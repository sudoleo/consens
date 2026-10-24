// =====================================================================
// consensus-insights.js
// Extrahiert aus templates/index.html (zweiter Inline-Script-Block).
// Credibility-Frames, Consensus-Insights-Popover, Spalten-Balancer.
// Kommuniziert ausschliesslich ueber window.* (siehe Exporte am Ende).
// Abhaengigkeiten (call-time): window.trackUmamiEvent.
// =====================================================================
        (function () {
          const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
            || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1); // iPadOS
          if (isIOS) document.documentElement.classList.add('ios');
        })();

        const credibilityFrameClasses = ["cred-very", "cred-largely", "cred-partially", "cred-hardly", "cred-not"];

        function getCredibilityClass(md) {
          if (!md) return null;
          const plain = String(md)
            .replace(/<[^>]*>/g, " ")
            .replace(/\*\*/g, "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
          const mapping = [
            { pattern: /the consensus answer is very credible/, cls: "cred-very" },
            { pattern: /the consensus answer is largely credible/, cls: "cred-largely" },
            { pattern: /the consensus answer is partially credible/, cls: "cred-partially" },
            { pattern: /the consensus answer is hardly credible/, cls: "cred-hardly" },
            { pattern: /the consensus answer is not credible/, cls: "cred-not" }
          ];

          for (const m of mapping) {
            if (m.pattern.test(plain)) return m.cls;
          }
          return null;
        }

        function resetCredibilityFrame(target) {
          // Strukturierte Auswertung (Verdict, Badges, Karten) immer mit zurücksetzen —
          // alle Aufrufer (Cancel, Fehler, neuer Lauf, Bookmarks, Demo) wollen beides.
          window.resetConsensusInsights?.();
          const frame = target?.classList?.contains("consensus-differences")
            ? target
            : target?.closest?.(".consensus-differences");
          if (!frame) return;
          frame.classList.remove("credibility-framed", ...credibilityFrameClasses);
        }

        function applyCredibilityFrame(target, md) {
          const frame = target?.classList?.contains("consensus-differences")
            ? target
            : target?.closest?.(".consensus-differences");
          if (!frame) return;
          resetCredibilityFrame(frame);
          const cls = getCredibilityClass(md);
          if (cls) {
            frame.classList.add("credibility-framed", cls);
          }
        }

        function colorizeCredibility(md) {
          if (!md) return md;
          const lines = md.trim().split("\n");
          if (!lines.length) return md;

          const first = lines[0].toLowerCase();
          const mapping = [
            { key: " very ", cls: "cred-very" },
            { key: " largely ", cls: "cred-largely" },
            { key: " partially ", cls: "cred-partially" },
            { key: " hardly ", cls: "cred-hardly" },
            { key: " not ", cls: "cred-not" }
          ];

          // Robust: prüft auf vollständige Satzfragmente
          let cls = null;
          if (first.includes("the consensus answer is")) {
            for (const m of mapping) {
              if (first.includes(m.key.trim())) { cls = m.cls; break; }
            }
          }

          if (cls) {
            // Markdown-Bold **…** in der Badge vermeiden, damit die Farbe klar lesbar bleibt
            lines[0] = lines[0].replace(/\*\*/g, "");
            lines[0] = `<span class="cred-badge ${cls}">${lines[0]}</span>`;
            return lines.join("\n");
          }
          return md;
        }

        window.getCredibilityClass = getCredibilityClass;
        window.applyCredibilityFrame = applyCredibilityFrame;
        window.resetCredibilityFrame = resetCredibilityFrame;
        window.colorizeCredibility = colorizeCredibility;

        // =====================================================================
        // Consensus Insights: Verdict-Header, Agreement-Badges, Differences-
        // Karten. Gespeist aus differences_data (strukturierte Ausgabe des
        // Differences-Calls). Fällt ohne Daten auf den Freitext-Pfad zurück.
        // =====================================================================
        (function () {
          const MODEL_BOX_IDS = Object.fromEntries(
            (window.App.modelPrefs || []).map(pref => [pref.key, pref.responseId])
          );

          function $(id) { return document.getElementById(id); }

          // Display filters never change the analysis or saved answer data.
          // Settings control both sentence highlights and source-reference verdicts.
          // Both choices are account settings (user-settings.js):
          // "consensus_highlights" (none or a filter below) and "claim_counts".
          const settings = window.App.userSettings;
          const MARKER_FILTERS = {
            all: "Highlight all model checks. Agreement is not proof of correctness.",
            contradictions: "Highlight model contradictions, including minor details.",
            concerns: "Highlight model contradictions, including minor details, and split model views.",
            critical: "Highlight critical model contradictions (red).",
          };
          const highlightSelect = $("consensusHighlightsSelect");
          const highlightHelp = $("consensusHighlightsHelp");
          // Only disagreements by default (2026-10-19, user decision): a mark
          // means "the models do not agree here". Agreement (green) and thin
          // coverage (grey) show only after the reader picks "All checks";
          // from 2026-10-12 to 2026-10-19 that was the default.
          const DEFAULT_HIGHLIGHT_MODE = "concerns";
          let highlightMode = DEFAULT_HIGHLIGHT_MODE;
          let markersVisible = true;
          const MARKERS_HIDDEN_CLASS = "consensus-markers-hidden";
          const claimCountsToggle = $("claimCountsSwitch");

          function restoreClaimCounts() {
            const show = settings.get("claim_counts") === true;
            document.body.classList.toggle("claim-counts-visible", show);
            if (claimCountsToggle) claimCountsToggle.checked = show;
            applyConsensusMarkerVisibility(storedConsensusMarkersVisible());
          }

          claimCountsToggle?.addEventListener("change", function () {
            settings.set("claim_counts", this.checked);
            document.body.classList.toggle("claim-counts-visible", this.checked);
            applyConsensusMarkerVisibility(storedConsensusMarkersVisible());
          });
          window.addEventListener("pageshow", restoreClaimCounts);

          function readMarkerPreferences() {
            const stored = settings.get("consensus_highlights");
            markersVisible = stored !== "none";
            // hasOwnProperty, not Object.hasOwn: this runs while the bundle
            // loads, and older engines (Chromium < 93) lack Object.hasOwn.
            highlightMode = Object.prototype.hasOwnProperty.call(MARKER_FILTERS, stored) ? stored : DEFAULT_HIGHLIGHT_MODE;
            return markersVisible;
          }

          function storedConsensusMarkersVisible() {
            return markersVisible;
          }

          function matchesHighlightFilter(mark) {
            // A provisional mark carries no verdict a filter could pick by:
            // it shows under every setting except "No highlights".
            if (highlightMode === "all" || mark.classList.contains("is-provisional")) return true;
            if (highlightMode === "contradictions") return !!mark.cxGroup?.hasContradiction;
            // Every contradiction the footer counts, minor ones included.
            if (highlightMode === "concerns" && mark.cxGroup?.hasContradiction) return true;
            return mark.classList.contains("is-major")
              || (highlightMode === "concerns" && mark.classList.contains("is-split"));
          }

          // An unpainted sentence of a checked text (passage-check.js,
          // .is-quiet) still opens its card on a click, but previews nothing.
          function passageIsVisible(group) {
            const first = group.spans[0];
            return markersVisible && !first.classList.contains("is-marker-filtered")
              && !first.classList.contains("is-quiet");
          }

          // Marks on a checked user message (passage-check.js, .pc-claim) keep
          // their own role and label; they only follow the painting.
          function syncMarkerPassageAccess(visible, root) {
            root.querySelectorAll(".cx-claim:not(.pc-claim)").forEach(function (mark) {
              const accessible = visible && !mark.classList.contains("is-marker-filtered");
              ["role", "tabindex", "aria-label"].forEach(function (attribute) {
                const dataKey = "markerVisible" + attribute.replace(
                  /(^|-)([a-z])/g,
                  function (_all, _dash, letter) { return letter.toUpperCase(); }
                );
                if (!accessible) {
                  if (mark.hasAttribute(attribute) && !(dataKey in mark.dataset)) {
                    mark.dataset[dataKey] = mark.getAttribute(attribute);
                  }
                  mark.removeAttribute(attribute);
                } else if (dataKey in mark.dataset) {
                  mark.setAttribute(attribute, mark.dataset[dataKey]);
                  delete mark.dataset[dataKey];
                }
              });
            });
          }

          function applyConsensusMarkerVisibility(visible, dismiss = false, root = document, fallbackBox = null) {
            const show = visible !== false;
            markersVisible = show;
            document.body.classList.toggle(MARKERS_HIDDEN_CLASS, !show);
            document.body.dataset.consensusHighlightMode = show ? highlightMode : "none";
            root.querySelectorAll(".cx-claim:not(.pc-claim)").forEach(function (mark) {
              const filtered = !matchesHighlightFilter(mark);
              mark.classList.toggle("is-marker-filtered", filtered);
              const group = mark.cxGroup;
              if (!group || group.spans[0] !== mark) return;
              if (!show || filtered || dismiss) {
                group.hover = false;
                applyPassageHover(group);
              }
              group.controls.forEach(function (entry) {
                if (!entry.isPassage) entry.el.classList.toggle("is-marker-filtered", filtered);
              });
              const control = activeControl(group);
              if (!control?.el.classList.contains("claim-badge")) return;
              const accessible = show && !filtered && !document.body.classList.contains("claim-counts-visible");
              ["role", "tabindex", "aria-label"].forEach(function (attr) { mark.removeAttribute(attr); });
              delete mark.dataset.markerVisibleRole;
              delete mark.dataset.markerVisibleTabindex;
              delete mark.dataset.markerVisibleAriaLabel;
              if (accessible) {
                mark.setAttribute("role", "button");
                mark.tabIndex = 0;
                mark.setAttribute("aria-label", passageLabel(group.spans, control.el.getAttribute("aria-label")));
              }
              if (!mark.dataset.cxKeyboard) {
                mark.dataset.cxKeyboard = "1";
                mark.addEventListener("keydown", function (event) {
                  if (!passageIsVisible(group)) return;
                  if (event.key !== "Enter" && event.key !== " ") return;
                  event.preventDefault();
                  activeControl(group)?.activate(event);
                });
                mark.addEventListener("focus", function () { focusPassage(group, mark); });
                mark.addEventListener("blur", function () { setPassageHover(group, false); });
              }
            });
            syncMarkerPassageAccess(show, root);
            const fallbackBoxes = fallbackBox ? [fallbackBox] : root.querySelectorAll(".consensus-claims-fallback");
            fallbackBoxes.forEach(function (box) {
              const rows = Array.from(box.querySelectorAll(".claims-fallback-row"));
              rows.forEach(function (row) {
                const include = highlightMode === "all"
                  || (highlightMode === "concerns" && row.dataset.coverage === "split");
                row.classList.toggle("is-marker-filtered", !include);
              });
              box.classList.toggle("is-marker-filtered", rows.length > 0
                && rows.every(row => row.classList.contains("is-marker-filtered")));
            });
            if (!show || dismiss) {
              closeClaimPopover();
              hideHoverPreview();
            }
            if (highlightSelect) highlightSelect.value = show ? highlightMode : "none";
            if (highlightHelp) highlightHelp.textContent = show
              ? MARKER_FILTERS[highlightMode]
              : "Sentence highlights are hidden. All analysis remains available in the details.";

          }

          function restoreConsensusMarkerVisibility() {
            applyConsensusMarkerVisibility(readMarkerPreferences());
          }

          function modelDisplayName(model) {
            const box = $(MODEL_BOX_IDS[model] || "");
            return (box && box.dataset.shortLabel) || model;
          }

          const LIVE_ANSWER_NAVIGATION = {
            canOpen: function (model) {
              return !!$(MODEL_BOX_IDS[model] || "");
            },
            open: function (model, quote) {
              jumpToModelAnswer(model, quote);
            }
          };

          function isMobileViewport() {
            return !!window.matchMedia?.("(max-width: 768px)").matches;
          }

          // --- Die vier Anzeigezustaende einer belegten Aussage --------------
          // Seit der Coverage-Judge JEDEN Satz beurteilt (2026-08-31), darf
          // eine duenn belegte Aussage nicht mehr einfach verschwinden - sonst
          // sieht sie aus wie ungepruefter Fliesstext, obwohl sie sehr wohl
          // angesehen wurde. Deshalb:
          //   split      geteilte Zustimmung (mindestens ein Modell widerspricht)
          //   supported  mindestens zwei Modelle stuetzen, keines widerspricht
          //   thin       zu wenige Modelle haben die Aussage ueberhaupt behandelt
          // Der vierte Zustand - der echte inhaltliche Widerspruch - kommt
          // nicht aus dem Claim, sondern aus der Differences-Analyse und
          // uebersteuert die Marke (siehe renderInlineMarkers).
          const MIN_CLAIM_SUPPORT = 2;
          const COVERAGE_STATES = ["supported", "split", "thin"];

          function claimCoverage(claim) {
            const state = String(claim?.coverage || "");
            if (COVERAGE_STATES.includes(state)) return state;
            // Alt-Snapshots ohne Coverage-Feld: aus den Zahlen ableiten. Die
            // frueheren Claims trugen immer mindestens zwei Stimmen, landen
            // hier also nie faelschlich auf "thin".
            if (claim.dissent.length) return "split";
            return claim.agree.length >= MIN_CLAIM_SUPPORT ? "supported" : "thin";
          }

          // --- Markdown-Auszeichnung entfernen -------------------------------
          // Anker und Zitate sind woertliche Kopien aus dem MARKDOWN-QUELLTEXT
          // der Antworten ("1. **Weltklasse:** ca. 1.300 Watt"). Gesucht und
          // angezeigt wird aber der GERENDERTE Text, in dem die Sternchen
          // laengst ein <strong> sind. Ein solcher Anker fand deshalb nie seine
          // Stelle im Konsens - und landete mitsamt sichtbarer Sternchen in der
          // Fallback-Liste "Key claims". Hier faellt dieselbe Auszeichnung weg,
          // die auch der Renderer schluckt.
          function inlineMarkdownSource(value) {
            return String(value || "")
              // Ein Anker aus einem Listenelement enthaelt haeufig dessen
              // Markdown-Zaehler (und das Kaestchen eines Checklistenpunkts).
              // Im gerenderten <li> ist er kein Textknoten.
              .replace(/(^|\n)[ \t]*(?:>[ \t]*)*(?:(?:[-*+]|\d+[.)])[ \t]+(?:\[[ xX]\][ \t]+)?|#{1,6}[ \t]+)?/g, "$1")
              .trim();
          }

          function stripMarkdown(value) {
            const source = inlineMarkdownSource(value);
            if (!source) return "";

            // Dieselbe Markdown-Engine wie fuer den Konsens liefert die
            // tatsaechlich sichtbare Textform. So bleiben literale Sternchen
            // erhalten, waehrend **fett** und Links korrekt reduziert werden.
            if (window.marked?.parseInline && window.DOMPurify?.sanitize) {
              const template = document.createElement("template");
              template.innerHTML = window.DOMPurify.sanitize(
                window.marked.parseInline(source),
                { ALLOWED_TAGS: ["strong", "em", "del", "code", "br"], ALLOWED_ATTR: [] }
              );
              return (template.content.textContent || "").replace(/[ \t]{2,}/g, " ").trim();
            }

            // Defensive Degradation, falls eine CDN-Library nicht geladen ist.
            return source
              .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
              .replace(/\*\*\*|\*\*|___|__|~~|`/g, "")
              .replace(/\*/g, "")
              .replace(/(^|[\s(["'])_([^_\n]+)_(?=$|[\s).,;:!?\]"'])/g, "$1$2")
              .replace(/[ \t]{2,}/g, " ")
              .trim();
          }

          function renderInlineMarkdown(element, value, prefix, suffix) {
            if (!element) return;
            // Anker aus aelteren Laeufen koennen eine abgesetzte Formel ohne
            // ihre "$$"-Zeilen enthalten. Ohne Trennzeichen bleibt sie
            // Quelltext; die Erkennung greift nur bei reinem LaTeX.
            const raw = inlineMarkdownSource(value);
            const source = window.ConsensusMath?.wrapBareLatex?.(raw) || raw;
            const before = prefix || "";
            const after = suffix || "";
            element.textContent = before;

            if (source && window.marked?.parseInline && window.DOMPurify?.sanitize) {
              const content = document.createElement("span");
              // A model's claim, in the language it was written in.
              content.setAttribute("data-i18n-skip", "");
              const hasEscapedLiteralStar = /\\\*/.test(source);
              const prepared = window.ConsensusMath?.prepareMarkdown
                ? window.ConsensusMath.prepareMarkdown(source)
                : source;
              content.innerHTML = window.DOMPurify.sanitize(
                window.marked.parseInline(prepared),
                { ALLOWED_TAGS: ["strong", "em", "del", "code", "br"], ALLOWED_ATTR: [] }
              );

              // Bereits gespeicherte Anker koennen aus einem Satz stammen, der
              // an einer Abkuerzung mitten in **fett** getrennt wurde. Marked
              // laesst die dadurch verwaisten Delimiter absichtlich als Text
              // stehen. In der reinen Anzeige sind sie aber nur kaputtes
              // Markdown; vollstaendige Sternchen-Paare wurden zu diesem
              // Zeitpunkt bereits in <strong>/<em> umgewandelt. Unterstriche
              // bleiben bewusst unangetastet (z. B. ein literales __init__).
              const textWalker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
              let textNode;
              while ((textNode = textWalker.nextNode())) {
                if (textNode.parentElement?.closest("code")) continue;
                // Ein explizit escaptes \* ist sichtbarer Inhalt, kein kaputter
                // Markdown-Delimiter. In diesem seltenen Fall greift die
                // Bereinigung fuer den ganzen kurzen Inline-Wert nicht.
                if (!hasEscapedLiteralStar) {
                  textNode.nodeValue = textNode.nodeValue.replace(/\*{2,3}/g, "");
                }
              }

              element.appendChild(content);
            } else {
              element.appendChild(document.createTextNode(stripMarkdown(source)));
            }
            if (after) element.appendChild(document.createTextNode(after));
            // Math ist nicht von marked/DOMPurify abhaengig. Auch wenn eine
            // dieser CDN-Libraries fehlt und oben der Plaintext-Pfad greift,
            // bleiben \(...\)/\[...\] echte KaTeX-Ausdruecke.
            window.ConsensusMath?.render?.(element);
          }

          // --- Textsuche: Whitespace kollabieren, Anführungszeichen vereinheitlichen
          const {
            normalizeForSearch,
            findRangesInText,
            findRangeInTextNode,
            searchVariants,
            sentenceBounds,
            locateAnchor
          } = window.App.consensusAnchor.create(stripMarkdown);
          // A link that only shows its address or its site becomes a source
          // pill after the marks are set (sources.js linkifyAgentSources), and
          // its text goes. Its words still find the sentence, but they are not
          // wrapped: a span inside left the page with them, and the hover card
          // of its sentence opened in the top left corner.
          function insideBareSourceLink(node) {
            const link = node.parentElement?.closest("a[href]");
            return Boolean(link) && Boolean(window.isBareSourceLink?.(link));
          }

          function wrapFlatRange(slices, start, end, className) {
            const spans = [];
            slices.forEach(function (slice) {
              if (slice.end <= start || slice.start >= end) return;
              if (insideBareSourceLink(slice.node)) return;
              let node = slice.node;
              const from = Math.max(start, slice.start) - slice.start;
              const to = Math.min(end, slice.end) - slice.start;
              if (to < node.nodeValue.length) node.splitText(to);
              if (from > 0) node = node.splitText(from);
              const span = document.createElement("span");
              span.className = className;
              node.parentNode.insertBefore(span, node);
              span.appendChild(node);
              spans.push(span);
            });
            // Bold, italics or links split one sentence into several spans. Only
            // the outer ends get padding and rounded corners; inner joins stay
            // flush, otherwise every <em>/<strong> edge reads as an extra space
            // ("( Årsrapport )", "omdannelse , das").
            spans.forEach(function (span, index) {
              if (index > 0) span.classList.add("cx-join-start");
              if (index < spans.length - 1) span.classList.add("cx-join-end");
            });
            return spans;
          }

          // Nur die Stelle des Streits traegt die Farbe (2026-10-19, User-
          // Vorgabe): in einem bestrittenen Satz die Worte, denen ein Modell
          // widerspricht (dissent[].target, vom Coverage-Judge benannt und
          // serverseitig gegen den Satz geprueft), nicht der ganze Satz. Der
          // Satz-Span bleibt das Steuerelement (Klick, Tastatur, Hover,
          // Highlights-Filter); .has-spot nimmt ihm nur die Flaeche. Findet
          // sich kein Ziel im Satz (aeltere Laeufe, verworfene Ziele), bleibt
          // der ganze Satz markiert.
          // Der Server liefert die Stelle als Originalspanne aus dem Markdown.
          // Beginnt oder endet sie in einer Auszeichnung ("Vincent Luis** won")
          // oder traegt sie einen Quellentag ("330 m.[S1]"), stehen im DOM nur
          // die sichtbaren Worte: Sternchen sind <strong>, der Tag ein
          // uebersprungener Chip. stripMarkdown laesst ungepaarte Sternchen
          // stehen, deshalb diese dritte Fassung.
          function visibleWords(value) {
            return String(value || "")
              .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
              .replace(/\[S?\d+(?:\s*,\s*S?\d+)*\]/gi, " ")
              .replace(/\*{1,3}|_{2,3}|~~|`/g, "")
              .replace(/\s+([.,;:!?])/g, "$1");
          }

          function wrapSpots(spans, targets) {
            const slices = [];
            let flat = "";
            spans.forEach(function (span) {
              const walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT);
              let node;
              while ((node = walker.nextNode())) {
                if (!node.nodeValue || node.parentElement?.closest(".cx-spot")) continue;
                slices.push({ node: node, start: flat.length, end: flat.length + node.nodeValue.length });
                flat += node.nodeValue;
              }
            });
            const ranges = [];
            targets.forEach(function (target) {
              // Nur ganze Fassungen: eine auf acht Woerter gekuerzte Variante
              // (searchVariants) markierte bloss einen Teil der Stelle.
              const needles = [stripMarkdown(target), target, visibleWords(target)]
                .map(normalizeForSearch).filter(Boolean);
              for (const needle of needles) {
                const hit = findRangesInText(flat, needle)[0];
                if (hit) { ranges.push(hit); break; }
              }
            });
            if (!ranges.length) return;
            ranges.sort(function (a, b) { return a.start - b.start; });
            const merged = [];
            ranges.forEach(function (range) {
              const last = merged[merged.length - 1];
              if (last && range.start <= last.end) last.end = Math.max(last.end, range.end);
              else merged.push({ start: range.start, end: range.end });
            });
            // Von hinten nach vorn: splitText verschiebt sonst die Offsets der
            // naechsten Stelle in denselben Textknoten.
            merged.reverse().forEach(function (range) {
              wrapFlatRange(slices, range.start, range.end, "cx-spot");
            });
            spans.forEach(function (span) { span.classList.add("has-spot"); });
          }

          // --- Popover / Bottom Sheet -------------------------------------
          let claimPopoverTrigger = null;
          let claimModalBackgroundState = [];

          function claimPopoverFocusables(pop) {
            return Array.from(pop?.querySelectorAll(
              'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            ) || []).filter(element => !element.hidden && element.getClientRects().length > 0);
          }

          function setClaimModalBackgroundInert(active) {
            if (active) {
              claimModalBackgroundState = Array.from(document.body.children)
                .filter(element => element.id !== "claimPopover" && element.id !== "claimSheetBackdrop")
                .map(element => ({ element: element, inert: element.inert }));
              claimModalBackgroundState.forEach(item => { item.element.inert = true; });
              return;
            }
            claimModalBackgroundState.forEach(item => {
              if (item.element.isConnected) item.element.inert = item.inert;
            });
            claimModalBackgroundState = [];
          }

          function onDocClick(event) {
            const pop = $("claimPopover");
            if (!pop || pop.hidden) return;
            if (pop.contains(event.target)) return;
            if (event.target.closest?.(".claim-badge")) return;
            closeClaimPopover();
          }

          function onKeyDown(event) {
            const pop = $("claimPopover");
            if (!pop || pop.hidden) return;
            if (event.key === "Escape") {
              event.preventDefault();
              closeClaimPopover();
              return;
            }
            if (event.key !== "Tab" || !pop.classList.contains("is-modal")) return;
            const focusables = claimPopoverFocusables(pop);
            if (!focusables.length) {
              event.preventDefault();
              pop.focus();
              return;
            }
            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first.focus();
            }
          }

          // Popover/Backdrop nach <body> verschieben: Vorfahren mit
          // backdrop-filter/transform erzeugen sonst einen eigenen Containing
          // Block und verschieben absolute/fixed-Koordinaten.
          function ensureOverlayOnBody(el) {
            if (el && el.parentElement !== document.body) {
              document.body.appendChild(el);
            }
            return el;
          }

          let pinnedCard = null;

          function closeClaimPopover(options) {
            const restoreFocus = options?.restoreFocus !== false;
            const pop = $("claimPopover");
            const backdrop = $("claimSheetBackdrop");
            pinnedCard = null;
            if (pop) {
              if (!pop.hidden) window.App?.popover?.closed(pop);
              pop.hidden = true;
              pop.removeAttribute("aria-modal");
              pop.removeAttribute("aria-labelledby");
              pop.removeAttribute("tabindex");
              // Content, place and shape stay until the next open, so the
              // card fades out as it was instead of collapsing first.
            }
            if (backdrop) backdrop.hidden = true;
            setClaimModalBackgroundInert(false);
            document.removeEventListener("click", onDocClick, true);
            document.removeEventListener("keydown", onKeyDown, true);
            if (restoreFocus && claimPopoverTrigger?.isConnected) {
              claimPopoverTrigger.focus({ preventScroll: true });
            }
            claimPopoverTrigger = null;
          }

          function modelsNotAddressingClaim(claim, modelsCompared) {
            if (!Array.isArray(modelsCompared)) return [];
            const addressed = new Set(claim.agree.concat(
              claim.dissent.map(function (item) { return item.model; })
            ));
            return modelsCompared.filter(function (model) { return !addressed.has(model); });
          }

          // Die festgehaltene Karte einer Marke (Klick, Enter). Am Rechner ist
          // es dieselbe Karte wie die Vorschau an derselben Stelle: stand die
          // Vorschau schon da, bleibt sie einfach stehen (is-instant), nur
          // werden ihre Logos und ihr Thema jetzt bedienbar. Auf dem Handy
          // ein Blatt vom unteren Rand, und der Satz rueckt knapp darueber.
          function openCard(anchorEl, spans, buildCard, kind) {
            const pop = ensureOverlayOnBody($("claimPopover"));
            const backdrop = ensureOverlayOnBody($("claimSheetBackdrop"));
            if (!pop) return;
            const previewed = !!(spans && hoverCard && !hoverCard.hidden
              && hoverGroup && hoverGroup.spans[0] === spans[0]);
            closeClaimPopover({ restoreFocus: false });
            hideHoverPreview({ instant: true });
            pop.replaceChildren();
            pop.style.left = pop.style.top = "";
            // One of the app's popovers (App.popover): any other menu closes.
            window.App?.popover?.register(pop, { close: () => closeClaimPopover({ restoreFocus: false }) });
            claimPopoverTrigger = anchorEl || document.activeElement;

            const close = document.createElement("button");
            close.type = "button";
            close.className = "claim-popover-close close-button";
            close.setAttribute("aria-label", "Close");
            close.innerHTML = window.App?.closeIcon?.() || "";
            close.addEventListener("click", closeClaimPopover);
            const card = buildCard({ interactive: true });
            pop.append(close, card);
            const title = card.querySelector(".cx-card-title, .cx-card-heading");
            if (title) {
              title.id = "claimPopoverTitle";
              pop.setAttribute("aria-labelledby", title.id);
            }

            const asModal = isMobileViewport();
            if (!asModal) pop.appendChild(cardPin(true, function () { closeClaimPopover(); }));
            pop.classList.toggle("is-modal", asModal);
            pop.classList.toggle("is-instant", previewed && !asModal);
            window.App?.popover?.opened(pop, { trigger: asModal ? null : anchorEl });
            pop.hidden = false;
            if (asModal) {
              pop.setAttribute("aria-modal", "true");
              pop.tabIndex = -1;
              setClaimModalBackgroundInert(true);
              if (backdrop) {
                backdrop.hidden = false;
                backdrop.addEventListener("click", closeClaimPopover, { once: true });
              }
              settleAboveSheet(pop, spans || (anchorEl ? [anchorEl] : []));
              requestAnimationFrame(function () { close.focus({ preventScroll: true }); });
            } else if (anchorEl) {
              // Wie die Vorschau: der Pfeil zeigt auf die strittigen Worte,
              // auch wenn die sichtbare Quote der Ausloeser war.
              pinnedCard = { anchor: spans ? cardAnchor(spans) : [anchorEl], around: spans || [anchorEl] };
              placeCard(pop, pinnedCard.anchor, pinnedCard.around);
            }
            if (previewed) {
              requestAnimationFrame(function () {
                requestAnimationFrame(function () { pop.classList.remove("is-instant"); });
              });
            }
            window.trackUmamiEvent?.("app_consensus_marker_opened", { kind: kind, previewed: previewed });
            setTimeout(function () {
              document.addEventListener("click", onDocClick, true);
              document.addEventListener("keydown", onKeyDown, true);
            }, 0);
          }

          // Auf dem Handy rueckt der Satz knapp ueber das Blatt, statt unter
          // ihm zu verschwinden; sein Anfang bleibt unter der Kopfzeile sichtbar.
          function settleAboveSheet(pop, around) {
            const lines = visibleRects(around);
            if (!lines.length) return;
            const sheetTop = window.innerHeight - pop.offsetHeight;
            const top = Math.min.apply(null, lines.map(function (r) { return r.top; }));
            const bottom = Math.max.apply(null, lines.map(function (r) { return r.bottom; }));
            const delta = Math.min(bottom - (sheetTop - 16), top - 72);
            if (!(delta > 0)) return;
            let scroller = around[0].parentElement;
            while (scroller && scroller !== document.body) {
              const overflow = getComputedStyle(scroller).overflowY;
              if (/auto|scroll|overlay/.test(overflow) && scroller.scrollHeight > scroller.clientHeight) break;
              scroller = scroller.parentElement;
            }
            if (!scroller || scroller === document.body) scroller = document.scrollingElement || document.documentElement;
            scroller.scrollBy({ top: delta, behavior: window.App.scrollBehavior?.() || "auto" });
          }

          // The same card for a checked sentence of the user's own message
          // (passage-check.js); options.spans names the marked sentence when
          // the anchor is a visible count, options.sideLabel the side the
          // text takes ("In your text").
          function openClaimPopover(claim, anchorEl, modelsCompared, answerNavigation, options = {}) {
            const spans = options.spans || anchorEl?.cxSpans || anchorEl?.cxGroup?.spans || null;
            openCard(anchorEl, spans, function (ctx) {
              return claimCard(claim, modelsCompared, Object.assign(ctx, {
                spans: spans,
                navigation: answerNavigation || LIVE_ANSWER_NAVIGATION,
                sideLabel: options.sideLabel,
                openInDrawer: options.openInDrawer
              }));
            }, "claim");
          }

          function openDifferencePopover(diff, spans, answerNavigation, openInDrawer) {
            openCard(spans[0], spans, function (ctx) {
              return differenceCard(diff, Object.assign(ctx, {
                navigation: answerNavigation || LIVE_ANSWER_NAVIGATION,
                openInDrawer: openInDrawer
              }));
            }, "difference");
          }

          // --- Sprung zur Originalantwort mit Zitat-Highlight ---------------
          // Markiert das Zitat und gibt das markierte Element zurück (oder null);
          // das Scrollen übernimmt der Aufrufer.
          function flashQuote(container, quote) {
            for (const needle of searchVariants(quote)) {
              const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
              let node;
              while ((node = walker.nextNode())) {
                if (!node.nodeValue || node.parentElement?.closest("code, pre, mark")) continue;
                const found = findRangeInTextNode(node, needle);
                if (!found) continue;
                const range = document.createRange();
                range.setStart(node, found.start);
                range.setEnd(node, found.end);
                const mark = document.createElement("mark");
                mark.className = "quote-flash";
                try {
                  range.surroundContents(mark);
                } catch (e) {
                  break;
                }
                setTimeout(function () {
                  const parent = mark.parentNode;
                  if (!parent) return;
                  while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
                  parent.removeChild(mark);
                  parent.normalize();
                }, 2400);
                return mark;
              }
              const blocks = container.querySelectorAll("p, li, h1, h2, h3, h4, td, blockquote");
              for (const block of blocks) {
                if (normalizeForSearch(block.textContent).includes(needle)) {
                  block.classList.add("quote-flash-block");
                  setTimeout(function () { block.classList.remove("quote-flash-block"); }, 2400);
                  return block;
                }
              }
            }
            return null;
          }

          function jumpToModelAnswer(model, quote) {
            if (window.App?.answerReader?.openLive(model, quote)) return;
            const box = $(MODEL_BOX_IDS[model] || "");
            if (!box) return;

            // Einzelantworten liegen inzwischen in jedem Modus hinter derselben
            // Disclosure. Den Zielbereich aufdecken, den Modus aber beibehalten.
            window.App?.agentMode?.showModelAnswers?.();

            // Der Klassenwechsel ist synchron; die folgenden Geometrie-Abfragen
            // erzwingen das Layout selbst. So hängt der Sprung auch in
            // gedrosselten Hintergrund-Tabs weder an rAF noch an Timern.
            const content = box.querySelector(".collapsible-content");
            const highlight = (content && quote) ? flashQuote(content, quote) : null;
            // Offset, damit der Box-Header ("Response from …") sichtbar bleibt
            const headerY = box.getBoundingClientRect().top + window.scrollY - 84;

            if (highlight) {
              const quoteY = highlight.getBoundingClientRect().top + window.scrollY;
              if (quoteY - headerY < window.innerHeight * 0.7) {
                // Zitat liegt nah am Boxanfang: Header und Zitat zusammen zeigen
                window.scrollTo({ top: Math.max(0, headerY), behavior: window.App.scrollBehavior?.() || "auto" });
              } else {
                // Zitat liegt tief in der Antwort: Zitat mittig anfahren
                window.scrollTo({ top: Math.max(0, quoteY - window.innerHeight / 2), behavior: window.App.scrollBehavior?.() || "auto" });
              }
            } else {
              window.scrollTo({ top: Math.max(0, headerY), behavior: window.App.scrollBehavior?.() || "auto" });
              box.classList.add("jump-flash");
              setTimeout(function () { box.classList.remove("jump-flash"); }, 2000);
            }
            window.trackUmamiEvent?.("app_consensus_jump_to_answer", { model: model, found_quote: !!highlight });
          }

          function storedAnswerNavigation(body) {
            function targetFor(model) {
              const turn = body.closest?.(".thread-history-turn");
              if (!turn) return null;
              return Array.from(turn.querySelectorAll(
                ".thread-history-models section[data-provider]"
              )).find(function (section) {
                return section.dataset.provider === model;
              }) || null;
            }

            return {
              canOpen: function (model) {
                // Asked while a hover card is built: without a reader on the
                // page the card still shows.
                if (window.App?.answerReader?.canOpenStored?.(body.closest?.(".thread-history-turn"), model)) return true;
                return !!targetFor(model);
              },
              open: function (model, quote) {
                if (window.App?.answerReader?.openStored?.(body.closest?.(".thread-history-turn"), model, quote)) return;
                const section = targetFor(model);
                if (!section) return;
                const panel = section.closest(".thread-history-panel");
                const turn = section.closest(".thread-history-turn");
                const tab = panel && turn
                  ? Array.from(turn.querySelectorAll(".consensus-tab")).find(function (candidate) {
                      return candidate.getAttribute("aria-controls") === panel.id;
                    })
                  : null;
                if (panel) panel.hidden = false;
                if (tab) tab.setAttribute("aria-expanded", "true");

                const content = section.querySelector(".thread-history-detail-body");
                const highlight = (content && quote) ? flashQuote(content, quote) : null;
                const headerY = section.getBoundingClientRect().top + window.scrollY - 84;
                if (highlight) {
                  const quoteY = highlight.getBoundingClientRect().top + window.scrollY;
                  const targetY = quoteY - headerY < window.innerHeight * 0.7
                    ? headerY
                    : quoteY - window.innerHeight / 2;
                  window.scrollTo({ top: Math.max(0, targetY), behavior: window.App.scrollBehavior?.() || "auto" });
                } else {
                  window.scrollTo({ top: Math.max(0, headerY), behavior: window.App.scrollBehavior?.() || "auto" });
                  section.classList.add("jump-flash");
                  setTimeout(function () { section.classList.remove("jump-flash"); }, 2000);
                }
                window.trackUmamiEvent?.("app_consensus_jump_to_answer", {
                  model: model,
                  found_quote: !!highlight,
                  stored_turn: true
                });
              }
            };
          }

          // Dasselbe fuer die Widerspruchs-Karten: ein archivierter Turn traegt
          // seine Karten in der eigenen Schublade (.thread-history-differences),
          // nicht im Live-Fuss. Die Karten entstehen erst NACH dieser Zeile
          // (der Turn wird von oben nach unten gebaut) — deshalb wird der
          // Container erst beim Klick gesucht, nicht beim Verankern.
          function storedDifferenceFocus(body) {
            return function (index) {
              const turn = body.closest?.(".thread-history-turn");
              if (turn && window.App?.answerReader?.openPanel('differences', null, turn, index)) return;
              const card = differenceCardAt(turn?.querySelector(".thread-history-differences"), index);
              if (!card) return;
              const panel = card.closest(".thread-history-panel");
              const tab = panel && turn
                ? Array.from(turn.querySelectorAll(".consensus-tab")).find(function (candidate) {
                    return candidate.getAttribute("aria-controls") === panel.id;
                  })
                : null;
              if (panel) panel.hidden = false;
              if (tab) tab.setAttribute("aria-expanded", "true");
              openDifferenceCard(card);
              card.scrollIntoView({ behavior: window.App.scrollBehavior?.() || "auto", block: "center" });
              card.classList.add("is-focused");
              setTimeout(function () { card.classList.remove("is-focused"); }, 2000);
            };
          }

          // --- Verdict: worüber, nicht wie viele -------------------------------
          // Aus differences[].claim wird eine kurze Themenangabe abgeleitet -
          // rein deterministisch, ohne zusätzlichen LLM-Call. "The models
          // contradict each other on 1 point" sagt dem Leser nichts darüber,
          // ob ihn der strittige Punkt betrifft; das Thema schon.
          const TOPIC_PREFIX =
            /^(?:the\s+models?\s+)?(?:dis)?agree(?:ment)?\s+(?:on|about)\s+|^(?:do|does|did|is|are|was|were|should|shall|can|could|will|would|has|have|whether|how|what|which|when|why)\b\s*/i;
          // Genau EIN Thema. Mehrere aneinandergereihte Fragmente plus
          // "+2 more" waren ueberladen; das eine wichtigste Thema darf die
          // vorhandene Breite dagegen voll nutzen und natuerlich umbrechen.
          // Eine feste Wortgrenze schnitt es auch auf breiten Screens mitten
          // im Satz ab.
          const TOPIC_MAX_SHOWN = 1;

          function toTopic(claim) {
            let text = String(claim || "").trim().replace(/[.?!]+$/, "");
            text = text.replace(TOPIC_PREFIX, "").trim();
            if (!text) return "";
            // Groß-/Kleinschreibung und der vollstaendige Wortlaut bleiben
            // unangetastet; CSS uebernimmt den Umbruch an der echten Kante.
            return text;
          }

          function topicList(entries) {
            // Schwerwiegendes zuerst: bleibt nur ein Thema sichtbar, muss es
            // das sein, das den Leser am ehesten betrifft.
            const sorted = entries.slice().sort(
              (a, b) => (b.severity === "major") - (a.severity === "major")
            );
            const topics = sorted.map(d => toTopic(d.claim)).filter(Boolean);
            if (!topics.length) return "";
            // Kein "+N more": WIE VIELE sagt die Detailzeile, WORUEBER sagt
            // dieses eine Thema. Beides in dieselbe Zeile zu quetschen war
            // genau die Ueberfrachtung, die den Fuss unlesbar gemacht hat.
            return topics.slice(0, TOPIC_MAX_SHOWN).join(" · ");
          }

          // --- Verdict-Balken --------------------------------------------------
          // Neutraler Glas-Balken: Score-Ring links (Farbe = Semantik),
          // Headline + Detailzeile daneben, Judge-Attribution rechts.
          const settledAgreements = new WeakSet();
          function renderVerdictHeader(differences, modelCount, agreement, judge) {
            const verdict = $("consensusVerdict");
            if (!verdict) return;
            const contradictions = differences.filter(d => d.type === "contradiction").length;
            const critical = differences.filter(d => d.type === "contradiction" && d.severity === "major").length;
            // Alte Bookmarks/Snapshots kennen keine Severity: dann keine
            // "critical"-Aussage machen statt fälschlich "none critical".
            const hasSeverity = differences.some(d => d.severity === "major" || d.severity === "minor");
            const emphases = differences.length - contradictions;
            const insufficient = agreement?.coverage_status === "insufficient";
            const hasScore = !insufficient && agreement && typeof agreement.score === "number";

            const boundedScore = hasScore
              ? Math.max(0, Math.min(100, agreement.score))
              : null;
            // Farbe und Text muessen dieselbe 0-100-Aussage tragen. Der
            // Widerspruchsstatus bleibt als getrennte Detailzeile sichtbar.
            // Nur alte Snapshots ohne Score fallen auf die Difference-Ampel
            // zurueck.
            const cls = insufficient ? "is-warn" : hasScore
              ? (boundedScore >= 65 ? "is-calm" : (boundedScore >= 40 ? "is-warn" : "is-alert"))
              : (contradictions === 0 ? "is-calm" : (critical > 0 ? "is-alert" : "is-warn"));
            verdict.classList.remove("is-calm", "is-warn", "is-alert");
            verdict.classList.add(cls);
            verdict.innerHTML = "";

            // Score-Anzeige; alte Bookmarks ohne Score behalten den kleinen Punkt.
            // Seit 2026-08-04 gesetzte Zahl plus feiner Messbalken statt
            // Conic-Ring auf getoenter Platte: die Zahl traegt die Aussage,
            // der Balken macht sie auf einen Blick vergleichbar, und die
            // Ampelfarbe bleibt die einzige Farbe im Fuss.
            if (hasScore) {
              const gauge = document.createElement("span");
              gauge.className = "verdict-gauge";
              gauge.style.setProperty("--val", String(boundedScore));
              gauge.title = modelCount === 1
                ? "Agreement score " + agreement.score + "/100 across 1 model"
                : "Agreement score " + agreement.score + "/100 across " + modelCount + " models";
              const score = document.createElement("span");
              score.className = "verdict-score";
              const num = document.createElement("span");
              num.className = "verdict-score-num";
              num.textContent = String(agreement.score);
              // Screenreader (und E2E-Check) lesen den vollen Score.
              const srUnit = document.createElement("span");
              srUnit.className = "visually-hidden";
              srUnit.textContent = "/100 agreement score";
              num.appendChild(srUnit);
              // Sichtbarer Nenner: eine nackte 28 sagt nicht, wovon sie 28 ist.
              // Das Wort "agreement" steht bereits in jeder Headline daneben,
              // eine zusaetzliche Bildunterschrift waere die dritte Wiederholung.
              const unit = document.createElement("span");
              unit.className = "verdict-score-unit";
              unit.setAttribute("aria-hidden", "true");
              unit.textContent = "/100";
              score.append(num, unit);
              const meter = document.createElement("span");
              meter.className = "verdict-meter";
              meter.setAttribute("aria-hidden", "true");
              const fill = document.createElement("span");
              fill.className = "verdict-meter-fill";
              meter.appendChild(fill);
              gauge.append(score, meter);
              verdict.appendChild(gauge);
              // Die Zahl zaehlt einmal pro Ergebnis hoch (CSS, siehe
              // components-consensus-visuals.css). Gemerkt wird das
              // agreement-Objekt: erneutes Rendern desselben Laufs (Run-View,
              // Projektionen) spielt es nicht noch einmal ab.
              const target = Number(agreement.score);
              if (Number.isInteger(target) && !settledAgreements.has(agreement)) {
                settledAgreements.add(agreement);
                num.style.setProperty("--score-target", String(target));
                gauge.classList.add("is-settling");
                setTimeout(() => gauge.classList.remove("is-settling"), 1000);
              }
            } else {
              const icon = document.createElement("span");
              icon.className = "verdict-icon";
              icon.setAttribute("aria-hidden", "true");
              verdict.appendChild(icon);
            }

            const contradictionTopics = topicList(
              differences.filter(d => d.type === "contradiction")
            );
            const emphasisTopics = topicList(
              differences.filter(d => d.type !== "contradiction")
            );

            const main = document.createElement("span");
            main.className = "verdict-main";
            const headline = document.createElement("span");
            headline.className = "verdict-headline";
            if (insufficient) {
              headline.textContent = "Insufficient evidence to assess agreement";
            } else if (hasScore && boundedScore >= 85) {
              headline.textContent = "High agreement";
            } else if (hasScore && boundedScore >= 65) {
              headline.textContent = "Strong agreement";
            } else if (hasScore && boundedScore >= 40) {
              headline.textContent = "Partial agreement";
            } else if (hasScore && boundedScore >= 20) {
              headline.textContent = "Low agreement";
            } else if (hasScore) {
              headline.textContent = "Very low agreement";
            } else if (contradictions === 0) {
              headline.textContent = "No direct contradictions";
            } else if (contradictionTopics) {
              headline.textContent = "Disputed: " + contradictionTopics;
            } else {
              headline.textContent = "The models contradict each other";
            }
            // Die Zeile wird auf eine Zeile gekuerzt (CSS); der volle Satz
            // bleibt im Tooltip erreichbar.
            headline.title = headline.textContent;
            main.appendChild(headline);

            // Detailzeile: erst wie schwer, dann wer geurteilt hat. Die
            // Modellzahl steht seit 2026-07-28 nur noch in den Lauf-Fakten
            // eine Zeile tiefer — sie zweimal in zwei grauen Zeilen
            // untereinander zu wiederholen war der halbe Ballast im Fuss.
            const detail = document.createElement("span");
            detail.className = "verdict-detail";
            if (contradictions === 0) {
              if (emphases > 0) {
                detail.textContent = emphasisTopics
                  ? "different emphasis on " + emphasisTopics + ", no contradictions"
                  : emphases === 1 ? "1 difference in emphasis, no contradictions"
                    : emphases + " differences in emphasis, no contradictions";
              } else {
                detail.textContent = "no contradictions found";
              }
            } else if (hasSeverity && critical > 0) {
              const crit = document.createElement("span");
              crit.className = "verdict-detail-crit";
              crit.textContent = critical + " critical";
              detail.appendChild(crit);
              const minor = contradictions - critical;
              if (minor > 0) {
                detail.appendChild(document.createTextNode(
                  minor === 1 ? " · 1 minor detail" : " · " + minor + " minor details"));
              }
            } else if (hasSeverity) {
              detail.textContent = contradictions === 1 ? "1 minor detail" : contradictions + " minor details";
            } else {
              detail.textContent = contradictions === 1 ? "1 disputed point" : contradictions + " disputed points";
            }
            if (contradictions > 0 && contradictionTopics) {
              detail.appendChild(document.createTextNode(
                " · disputed: " + contradictionTopics));
            }

            if (agreement && typeof agreement.coverage_percent === "number") {
              const coverageNote = document.createElement("span");
              coverageNote.className = "verdict-coverage";
              coverageNote.textContent = " · Coverage: " + agreement.scored_claims + "/"
                + agreement.total_claims + " claims (" + agreement.coverage_percent + "%)";
              if (agreement.evidence_incomplete) coverageNote.textContent += " · evidence incomplete";
              coverageNote.title = "Claims assessed against at least two model responses. Coverage is separate from agreement.";
              detail.appendChild(coverageNote);
            }

            // Transparenz: welche Modellfamilie die Analyse geliefert hat
            // (seit 2026-10-04 nicht mehr zwingend eine andere als die
            // Engine). Als Nachsatz derselben Zeile statt als rechts
            // ausgerichteter Zweizeiler — eine Fußnote, die einen eigenen
            // Block bekommt, liest sich wie eine zweite Überschrift.
            if (judge && judge.provider) {
              const note = document.createElement("span");
              note.className = "verdict-judge";
              note.title = "A separate check compares the consensus with every model answer.";
              const provider = document.createElement("span");
              provider.textContent = "analysis by " + judge.provider
                + (judge.tier === "pro" ? " (Pro)" : "");
              const sub = document.createElement("span");
              sub.className = "verdict-judge-sub";
              sub.textContent = "separate judge pass";
              note.append(provider, sub);
              if (detail.childNodes.length) {
                detail.appendChild(document.createTextNode(" · "));
              }
              detail.appendChild(note);
            }
            main.appendChild(detail);
            verdict.appendChild(main);
            verdict.hidden = false;
          }

          // --- Agreement-Badges in der Konsens-Antwort -----------------------
          function claimBadgeLabel(claim, modelsCompared) {
            const t = window.App.t;
            const agreeCount = claim.agree.length;
            const total = agreeCount + claim.dissent.length;
            // Die Formulierung bleibt fuer Screenreader und den Detaildialog
            // erhalten. Die sichtbare Erklaerung liefert allein die formatierte
            // Hover-Vorschau, nicht zusaetzlich ein nativer Browser-Tooltip.
            // Teil fuer Teil durch App.t: Das Label steht in der Antwort, und
            // dort uebersetzt i18n.js nichts (data-i18n-skip, docs/i18n.md).
            const notAddressed = modelsNotAddressingClaim(claim, modelsCompared).length;
            const open = " " + t("— open details");
            if (claimCoverage(claim) === "thin") {
              const compared = total + notAddressed;
              return (compared
                ? t("Too few models addressed this — only {total} of {compared}", { total, compared })
                : t("Too few models addressed this")) + open;
            }
            const head = claim.dissent.length
              ? t("{length} of {total} models support this", { length: agreeCount, total })
              : t("All {total} models that address this agree", { total });
            const tail = !notAddressed ? ""
              : "; " + (notAddressed === 1
                ? t("1 did not address it")
                : t("{count} did not address it", { count: notAddressed }));
            return head + tail + open;
          }

          // Eine Marke mit role="button" ersetzt ihren Text durch ihren Namen:
          // Ohne den Satz darin las ein Screenreader an den strittigen Stellen
          // nur das Urteil vor (docs/a11y-audit-2026-10-23.md, B1). Gleiche
          // Form wie ein Satz eines geprueften Texts (passage-check.js).
          function passageLabel(spans, label) {
            const text = spans.map(function (span) { return span.textContent; })
              .join("").replace(/\s+/g, " ").trim();
            return text ? window.App.t("“{text}” – {label}", { text, label }, "marked sentence") : label;
          }

          // Inline counts are opt-in; the marked passage remains accessible
          // when the badge is hidden. Fallback rows retain their detail button.
          function makeBadge(claim, modelsCompared, answerNavigation, options) {
            const badge = document.createElement("button");
            badge.type = "button";
            const coverage = claimCoverage(claim);
            badge.className = "claim-badge"
              + (claim.dissent.length ? " has-dissent" : "")
              + (coverage === "thin" ? " is-thin" : "");
            const agreeCount = claim.agree.length;
            const total = agreeCount + claim.dissent.length;
            const ratio = document.createElement("span");
            ratio.className = "claim-ratio";
            // Bei duenner Abdeckung steht hier BEWUSST keine Quote: "1/1"
            // liest sich wie einstimmige Zustimmung, obwohl genau das Gegenteil
            // gemeint ist. Der Strich sagt "kein belastbares Votum" und ist als
            // einziger Zustand ohne Zahl auf einen Blick unterscheidbar.
            ratio.textContent = coverage === "thin" ? "–" : agreeCount + "/" + total;
            ratio.setAttribute("aria-hidden", "true");
            badge.appendChild(ratio);
            badge.setAttribute("aria-haspopup", "dialog");
            // Tastatur/Screenreader: sprechendes Label statt nacktem "4/6".
            badge.setAttribute("aria-label", claimBadgeLabel(claim, modelsCompared));
            badge.addEventListener("click", function (event) {
              event.stopPropagation();
              openClaimPopover(claim, badge, modelsCompared, answerNavigation, options);
            });
            return badge;
          }

          // --- Inline-Marker: Widersprüche und Claims im Antworttext ---------
          // Seit 2026-08-15 (User-Vorgabe) trägt die Textstelle einen farbigen
          // Textmarker statt einer Unterstreichung, und der Punkt daneben ist
          // ersatzlos weg: die Farbe sagt bereits alles, was der Punkt sagen
          // konnte. Bei einer Differenz ist die angestrichene Passage deshalb
          // selbst das Steuerelement (role="button"), bei einem Claim bleibt
          // die Quote daneben das sichtbare Ziel.

          // Ein Satz wird höchstens einmal dekoriert. Widersprüche laufen
          // deshalb zuerst (stärkere Stufe), Claim-Badges hängen sich danach an
          // denselben Satz, ohne ihn ein zweites Mal zu unterstreichen.
          function findOverlap(marked, start, end) {
            return marked.find(function (r) { return start < r.end && end > r.start; }) || null;
          }

          function differenceKind(diff) {
            const isMajor = diff.type === "contradiction" && diff.severity === "major";
            return diff.type === "contradiction"
              ? (isMajor ? "The models contradict each other here" : "The models differ on a detail here")
              : "The models set a different focus here";
          }

          function diffMarkerLabel(diff) {
            const t = window.App.t;
            return t(differenceKind(diff)) + (diff.claim ? ": " + diff.claim : "") + " " + t("— open details");
          }

          // Öffnet die zugehörige Karte im Differences-Überblick und hebt sie
          // kurz hervor (vom Thema der festgehaltenen Karte aus). Das
          // <details> darüber (Phase 4) wird mit aufgeklappt.
          function focusDifferenceCard(index) {
            if (window.App?.answerReader?.openPanel('differences', null, null, index)) return;
            const card = differenceCardAt($("differencesCards"), index);
            if (!card) return;
            const panel = card.closest("details.consensus-differences-panel");
            if (panel) panel.open = true;
            openDifferenceCard(card);
            card.scrollIntoView({ behavior: window.App.scrollBehavior?.() || "auto", block: "center" });
            card.classList.add("is-focused");
            setTimeout(function () { card.classList.remove("is-focused"); }, 2000);
          }

          // Stufen der Satzmarkierung, schwach nach stark. Treffen zwei Marken
          // denselben Satz, gewinnt die staerkere die Linie - sonst stand
          // neben einem gelben 2/4-Badge eine graue Linie.
          const MARK_LEVELS = {
            // Ganz unten die duenne Abdeckung: eine Aussage, die kaum ein
            // Modell behandelt hat, darf nie eine staerkere Marke verdraengen.
            "is-thin": -1,
            "is-unanimous": 0,
            "is-minor": 1,
            "is-split": 2,
            "is-major": 3
          };

          // Markiert eine Textstelle satzweise und liefert den letzten Span
          // zurück (dahinter wird der Marker/das Badge eingehängt).
          function markSentence(container, anchor, severityClass, marked, occurrence) {
            const hit = locateAnchor(container, anchor, occurrence);
            if (!hit) return null;

            const bounds = sentenceBounds(hit.flat, hit.start, hit.end);
            if (bounds.end <= bounds.start) return null;

            // Derselbe Satz wird nicht zweimal dekoriert (ein Widerspruch und
            // ein Claim können auf dieselbe Stelle zeigen). Das zweite Element
            // hängt sich an die bereits erzeugten Spans an - hebt die Linie
            // aber auf seine Stufe an, wenn sie schwaecher ist als seine Marke.
            const existing = findOverlap(marked, bounds.start, bounds.end);
            if (existing) {
              if (MARK_LEVELS[severityClass] > MARK_LEVELS[existing.severity]) {
                existing.spans.forEach(function (span) {
                  span.classList.remove(existing.severity);
                  span.classList.add(severityClass);
                });
                existing.severity = severityClass;
              }
              return { spans: existing.spans, block: hit.block };
            }

            const spans = wrapFlatRange(
              hit.slices, bounds.start, bounds.end, "cx-claim " + severityClass
            );
            // Nothing left to wrap (the sentence is a bare source link): no
            // mark, the claim goes to the list like any unanchored one.
            if (!spans.length) return null;
            marked.push({
              start: bounds.start, end: bounds.end, spans: spans, severity: severityClass
            });
            return { spans, block: hit.block };
          }

          function insertAfterMark(result, el) {
            const last = result.spans[result.spans.length - 1];
            if (last && last.parentNode) {
              last.parentNode.insertBefore(el, last.nextSibling);
            } else {
              result.block.appendChild(el);
            }
          }

          // --- Passage und Marker aneinander koppeln --------------------------
          // Die markierte Passage ist ein ganzer Satz und damit das weitaus
          // groesste Ziel: Vorschau, Zeigefinger, Klick haengen an ihr. Der
          // Hover wirkt in beide Richtungen, damit sichtbar wird,
          // welches Badge zu welchem Satz gehoert (ein Absatz kann mehrere
          // tragen). Wo ein Badge steht, bleibt es das fokussierbare
          // Steuerelement und die Passage ist nur ein zusaetzlicher Mausweg;
          // an einer Differenz gibt es daneben nichts mehr, deshalb wird dort
          // die Passage selbst fokussierbar (attachPassageControl).
          function applyPassageHover(group) {
            group.spans.forEach(function (span) {
              span.classList.toggle("is-hovered", group.hover);
            });
            group.controls.forEach(function (ctrl) {
              ctrl.el.classList.toggle("is-linked-hover", group.hover);
            });
          }

          function setPassageHover(group, on) {
            if (on && !passageIsVisible(group)) return;
            group.hover = on;
            if (on) {
              if (hoverGroup === group) window.clearTimeout(leaveTimer);
              applyPassageHover(group);
              scheduleHoverPreview(group);
              return;
            }
            if (hoverGroup === group) {
              // Steht die Karte, ist der Zeiger vielleicht auf dem Weg in sie
              // hinein (leaveHoverPreview); sonst gibt es nichts abzuwarten.
              if (hoverCard && !hoverCard.hidden) {
                leaveHoverPreview(group);
                return;
              }
              hideHoverPreview();
            }
            // Der Weg von einem Span zum naechsten (ein Satz kann in mehrere
            // Spans zerfallen) oder zum Marker feuert leave/enter nacheinander.
            // Ein Frame Verzoegerung verhindert das Flackern dazwischen.
            requestAnimationFrame(function () {
              if (!group.hover) applyPassageHover(group);
            });
          }

          // Ueberlappende Markierungen haben mehrere Controls. Sichtbar ist
          // immer nur eines: das zugunsten des Claims zurueckgetretene
          // Difference-Control (suppressed) darf weder den Klick abfangen noch
          // die Hover-Vorschau stellen.
          function activeControl(group) {
            return group.controls.find(function (item) {
              return !item.suppressed && !item.el.hidden
                && item.el.getAttribute("aria-hidden") !== "true";
            }) || group.controls[0] || null;
          }

          // `interactive: false`: hover only. A provisional mark opens nothing,
          // and a checked sentence of the user's text has its own click
          // (passage-check.js).
          function passageGroup(spans, interactive = true) {
            if (spans[0].cxGroup) return spans[0].cxGroup;
            const group = { spans: spans, controls: [], hover: false };
            spans.forEach(function (span) {
              span.cxGroup = group;
              span.addEventListener("mouseenter", function () { if (canHoverPassages()) setPassageHover(group, true); });
              span.addEventListener("mouseleave", function () { setPassageHover(group, false); });
              if (!interactive) return;
              span.classList.add("is-interactive");
              span.addEventListener("click", function (event) {
                if (!passageIsVisible(group)) return;
                // Quellenchips und [S1]-Links im Satz behalten Vorrang, und wer
                // Text markiert, will ihn kopieren und nichts oeffnen.
                if (event.target.closest("a, button")) return;
                const selection = window.getSelection?.();
                if (selection && !selection.isCollapsed) return;
                const target = activeControl(group);
                if (target) target.activate(event);
              });
            });
            return group;
          }

          // Hover nur auf Geraeten mit echtem Zeiger, dieselbe Abfrage wie die
          // Hover-Kapsel im CSS (codebase-map §8): ein Handy, das irgendeinen
          // feinen Zeiger meldet (any-pointer), zaehlt nicht. Der Klick auf die
          // Passage bleibt dagegen auch auf Touch aktiv.
          function canHoverPassages() {
            return !!window.matchMedia?.("(hover: hover) and (pointer: fine)").matches;
          }

          // Fokus zeigt die Vorschau nur, wenn der Leser ihn mit der Tastatur
          // dorthin gebracht hat (Tab, also :focus-visible). Ein Tippen
          // fokussiert den Satz ebenfalls (tabindex), und ein geschlossenes
          // Sheet oder eine geschlossene Karte gibt den Fokus an ihn zurueck
          // (model-answer-reader.js, closeClaimPopover): beides ist keine Bitte
          // um die Vorschau. Auf dem Handy stand sie sonst nach dem Schliessen
          // des grossen Fensters von selbst da.
          let tabbing = false;
          document.addEventListener("keydown", function (event) { tabbing = event.key === "Tab"; }, true);
          document.addEventListener("pointerdown", function () { tabbing = false; }, true);
          function focusShowsPreview(el) {
            if (!tabbing || !canHoverPassages()) return false;
            try { return el.matches(":focus-visible"); } catch (_) { return true; }
          }
          function focusPassage(group, el) {
            if (focusShowsPreview(el)) setPassageHover(group, true);
          }

          // --- Vorschau beim Hovern -------------------------------------------
          // Die Marke sagt "hier ist etwas", aber nicht was. Wer mit der Maus
          // darauf verweilt, bekommt die Karte der Marke, und die Karte ist
          // erreichbar: wer mit dem Zeiger hineinfaehrt, behaelt sie und kann
          // ihre Wege nehmen (Logos, Fusszeile). Vorher fing sie keine Maus,
          // verschwand auf dem Weg zu ihr, und dass ein Klick sie festhaelt,
          // musste man erraten (Max 2026-10-23). Der Klick haelt sie weiter
          // fest (openCard), fuer Touch und Tastatur ist das der Weg. Wer von
          // einer Marke zur naechsten zieht, wartet nicht ein zweites Mal
          // (HOVER_WARM_MS), wie bei den Tooltips (tooltip.js); steht noch eine
          // Karte, wechselt sie erst nach HOVER_SWITCH_MS, damit eine Marke auf
          // dem Weg in die Karte sie nicht wegnimmt.
          const HOVER_DELAY_MS = 130;
          const HOVER_WARM_MS = 400;
          const HOVER_SWITCH_MS = 90;
          const HOVER_LEAVE_MS = 260;
          let hoverCard = null;
          let hoverTimer = null;
          let leaveTimer = null;
          let hoverGroup = null;
          let hoverHiddenAt = 0;

          function ensureHoverCard() {
            if (hoverCard && hoverCard.isConnected) return hoverCard;
            hoverCard = document.createElement("div");
            hoverCard.className = "insight-preview";
            // Tastatur und Screenreader bekommen dieselbe Karte als Dialog
            // (Enter, openCard); diese hier gehoert dem Zeiger.
            hoverCard.setAttribute("aria-hidden", "true");
            hoverCard.hidden = true;
            // Maus-, nicht Pointer-Ereignisse wie an den Saetzen: pointerenter
            // kaeme vor dem mouseleave des Satzes, und der naehme die Karte
            // unter dem Zeiger wieder weg.
            hoverCard.addEventListener("mouseenter", holdHoverPreview);
            hoverCard.addEventListener("mouseleave", function () {
              if (hoverGroup && !hoverCard.hidden) setPassageHover(hoverGroup, false);
            });
            document.body.appendChild(hoverCard);
            return hoverCard;
          }

          // Zeiger weg von Satz und Karte: die Karte geht erst nach einem
          // Moment, sonst erreichte er sie nie. Ist er zurueck oder hat eine
          // andere Marke uebernommen, bleibt es dabei.
          function leaveHoverPreview(group) {
            window.clearTimeout(leaveTimer);
            leaveTimer = window.setTimeout(function () {
              if (group.hover) return;
              if (hoverGroup === group && hoverCard?.matches(":hover")) {
                holdHoverPreview();
                return;
              }
              if (hoverGroup === group) hideHoverPreview();
              applyPassageHover(group);
            }, HOVER_LEAVE_MS);
          }

          // Der Zeiger ist in der Karte: sie bleibt, ihr Satz bleibt
          // angestrichen, und eine Marke, die er auf dem Weg gestreift hat,
          // kommt nicht mehr.
          function holdHoverPreview() {
            const group = hoverGroup;
            if (!group || !hoverCard || hoverCard.hidden) return;
            window.clearTimeout(leaveTimer);
            window.clearTimeout(hoverTimer);
            group.hover = true;
            applyPassageHover(group);
          }

          // Ein Weg aus der Vorschau (Logo, Fusszeile): sie geht, und der
          // Fokus steht an ihrer Marke, damit der Leser ihn beim Schliessen
          // dorthin zurueckgibt.
          function leavePreviewFor(group) {
            group.hover = false;
            hideHoverPreview({ instant: true });
            applyPassageHover(group);
            const control = activeControl(group)?.el;
            if (control?.isConnected && control.matches("button, [tabindex]")) control.focus({ preventScroll: true });
          }

          // Der Inhalt bleibt, bis die naechste Vorschau kommt: die Karte
          // blendet aus, wie sie war. Haelt ein Klick sie fest, geht sie ohne
          // Ausblenden (instant), denn an ihrer Stelle steht im selben Moment
          // die festgehaltene Karte.
          function hideHoverPreview(options) {
            window.clearTimeout(hoverTimer);
            window.clearTimeout(leaveTimer);
            const group = hoverGroup;
            hoverTimer = null;
            hoverGroup = null;
            // Wartete die Karte noch auf den Zeiger, haengt am Satz noch der
            // Anstrich; der ginge sonst erst mit dem abgebrochenen Timer.
            if (group && !group.hover) applyPassageHover(group);
            if (!hoverCard || hoverCard.hidden) return;
            hoverCard.classList.toggle("is-instant", options?.instant === true);
            hoverCard.hidden = true;
            hoverHiddenAt = Date.now();
          }

          // Marks of `root` are redrawn or taken off: a preview of one of them
          // (or of a mark already gone) goes too, any other stays.
          function hidePreviewWithin(root) {
            const hovered = hoverGroup?.spans[0];
            if (hovered && (!root || !hovered.isConnected || root.contains(hovered))) hideHoverPreview();
          }

          // Was die Karte verankern kann: Spans, die im Dokument stehen und
          // Flaeche haben. Ein abgehaengter Span misst ueberall 0 und setzte
          // die Karte in die linke obere Ecke.
          function placedSpans(group) {
            return group.spans.filter(function (span) {
              return span.isConnected && span.getClientRects().length > 0;
            });
          }

          function visibleRects(elements) {
            const rects = [];
            elements.forEach(function (el) {
              Array.from(el?.getClientRects?.() || []).forEach(function (rect) {
                if (rect.width > 0 || rect.height > 0) rects.push(rect);
              });
            });
            return rects;
          }

          // Worauf der Pfeil zeigt: die strittigen Worte (.cx-spot), sonst der
          // ganze Satz. Nur sein erster Span war zu wenig: ein Satz mit
          // **fett** oder Link zerfaellt in mehrere, und die Karte hielt
          // dessen erste Zeile fuer die Stelle des Streits (stand ueber dem
          // Satz und hing rechts aus dem Text, Max 2026-10-23).
          function cardAnchor(spans) {
            for (const span of spans) {
              const spot = span.querySelector?.(".cx-spot");
              if (spot && spot.getClientRects().length) return [spot];
            }
            const placed = spans.filter(function (span) { return span.getClientRects().length; });
            return placed.length ? placed : spans.slice(0, 1);
          }

          // Das erste Stueck einer Zeile der Marke: der obersten (Karte darueber)
          // oder der untersten (Karte darunter).
          function lineStart(rects, bottom) {
            const edge = bottom
              ? Math.max.apply(null, rects.map(function (r) { return r.top; }))
              : Math.min.apply(null, rects.map(function (r) { return r.top; }));
            return rects.filter(function (r) { return Math.abs(r.top - edge) <= Math.max(r.height / 2, 1); })
              .reduce(function (a, b) { return a && a.left <= b.left ? a : b; }, null)
              || rects[bottom ? rects.length - 1 : 0];
          }

          // Unten endet der Platz am Eingabefeld (oder am Hinweis, der es in
          // der Demo ersetzt), nicht am Fensterrand: dort lag die Karte sonst
          // halb darunter.
          const CARD_GAP = 12;
          const CARD_EDGE = 12;

          function cardFloor(below) {
            let floor = window.innerHeight - CARD_EDGE;
            document.querySelectorAll(".chat-input-container, #postDemoLoginPrompt").forEach(function (el) {
              if (!el.getClientRects().length) return;
              const top = el.getBoundingClientRect().top;
              if (top >= below && top < window.innerHeight) floor = Math.min(floor, top - CARD_EDGE);
            });
            return floor;
          }

          // Die Karte verdeckt nie den Satz, um den es geht: sie steht ueber
          // seiner ersten oder unter seiner letzten Zeile, auf der Seite der
          // strittigen Worte, und ihr Pfeil zeigt auf diese Worte. Ihr Text
          // beginnt buendig unter dem Wort, auf das der Pfeil zeigt, bleibt
          // aber im Textblock: weder links davon noch rechts hinaus.
          // Dieselbe Rechnung fuer Vorschau und festgehaltene Karte, damit
          // ein Klick sie an Ort und Stelle laesst.
          function placeCard(card, anchors, around) {
            const marks = visibleRects(anchors);
            const lines = visibleRects(around && around.length ? around : anchors);
            if (!marks.length || !lines.length) return;
            card.style.left = "0px";
            card.style.top = "0px";
            const width = card.offsetWidth;
            const height = card.offsetHeight;
            const top = Math.min.apply(null, lines.map(function (r) { return r.top; }));
            const bottom = Math.max.apply(null, lines.map(function (r) { return r.bottom; }));
            const floor = cardFloor(bottom);
            const fitsBelow = bottom + CARD_GAP + height <= floor;
            const fitsAbove = top - CARD_GAP - height >= CARD_EDGE;
            const markTop = Math.min.apply(null, marks.map(function (r) { return r.top; }));
            const markBottom = Math.max.apply(null, marks.map(function (r) { return r.bottom; }));
            // Steht die Stelle in der ersten Zeile eines laengeren Satzes,
            // liegt der kuerzere Weg ueber ihm.
            const nearTop = markTop - top < 4 && bottom - markBottom > 4;
            let below = nearTop ? !fitsAbove && fitsBelow : fitsBelow || !fitsAbove;
            if (!fitsAbove && !fitsBelow) below = floor - bottom >= top;
            let y = below ? bottom + CARD_GAP : top - CARD_GAP - height;
            if (!fitsAbove && !fitsBelow) y = Math.max(CARD_EDGE, Math.min(y, floor - height));

            const target = lineStart(marks, below);
            const inset = parseFloat(getComputedStyle(card).paddingLeft) || 0;
            const block = anchors[0].closest("p, li, td, th, dd, dt, blockquote, h1, h2, h3, h4, h5, h6");
            const box = block ? block.getBoundingClientRect() : null;
            const viewMax = Math.max(CARD_EDGE, window.innerWidth - width - CARD_EDGE);
            const minLeft = Math.min(Math.max(CARD_EDGE, (box ? box.left : target.left) - inset), viewMax);
            // Ein Wort am Zeilenende zog die Karte sonst ueber den Rand des
            // Texts hinaus; ein Block schmaler als die Karte (Tabellenzelle)
            // begrenzt sie nicht.
            const columnMax = box ? box.right + inset - width : viewMax;
            const maxLeft = columnMax >= minLeft ? Math.min(columnMax, viewMax) : viewMax;
            const left = Math.max(minLeft, Math.min(target.left - inset, maxLeft));
            const arrow = Math.max(20, Math.min(target.left + Math.min(target.width / 2, 28) - left, width - 20));

            card.dataset.placement = below ? "below" : "above";
            card.style.setProperty("--cx-arrow-x", arrow + "px");
            card.style.setProperty("--popover-origin-x", arrow + "px");
            card.style.setProperty("--popover-origin-y", below ? "0%" : "100%");
            card.style.setProperty("--popover-shift", below ? "-4px" : "4px");
            card.style.left = (left + window.scrollX) + "px";
            card.style.top = (y + window.scrollY) + "px";
          }

          function showHoverPreview(group) {
            if (!passageIsVisible(group)) return;
            // Die offene Karte sagt schon alles: keine zweite daneben.
            const pop = $("claimPopover");
            if (pop && !pop.hidden) return;
            const spans = placedSpans(group);
            if (!spans.length) return;
            const active = activeControl(group);
            const build = (active && active.preview) ? active
              : group.controls.find(function (c) { return c.preview && !c.suppressed; });
            if (!build || !build.preview) return;
            const card = ensureHoverCard();
            card.classList.remove("is-instant");
            card.replaceChildren(build.preview({ interactive: true, close: function () { leavePreviewFor(group); } }));
            if (build.pinnable !== false) {
              card.appendChild(cardPin(false, function () {
                const target = activeControl(group);
                if (target?.isPassage) (group.spans[0] || target.el).click();
                else target?.activate();
              }));
            }
            // Nur fuer den Zeiger: der Tabulator erreicht dieselben Wege in
            // der festgehaltenen Karte.
            card.querySelectorAll("button, a[href]").forEach(function (el) { el.tabIndex = -1; });
            card.hidden = false;
            placeCard(card, cardAnchor(spans), spans);
          }

          function scheduleHoverPreview(group) {
            const shown = hoverCard && !hoverCard.hidden ? hoverGroup : null;
            if (shown === group) return;
            window.clearTimeout(hoverTimer);
            if (!shown) hoverGroup = group;
            const warm = !!hoverCard && Date.now() - hoverHiddenAt < HOVER_WARM_MS;
            hoverTimer = window.setTimeout(function () {
              if (!group.hover) return;
              const previous = hoverGroup;
              if (previous && previous !== group && !previous.hover) applyPassageHover(previous);
              hoverGroup = group;
              showHoverPreview(group);
            }, shown ? HOVER_SWITCH_MS : warm ? 0 : HOVER_DELAY_MS);
          }

          // Am Rechner bleibt die festgehaltene Karte an ihren Worten, wenn
          // der Verlauf scrollt.
          function refreshPinnedCard() {
            const pop = $("claimPopover");
            if (!pinnedCard || !pop || pop.hidden || pop.classList.contains("is-modal")) return;
            if (!pinnedCard.anchor[0]?.isConnected) {
              closeClaimPopover({ restoreFocus: false });
              return;
            }
            placeCard(pop, pinnedCard.anchor, pinnedCard.around);
          }

          // Scrolling can arrive just AFTER mouseenter and cancel its timer.
          // Once the layout settles, a card whose passage is still under the
          // pointer (or the keyboard focus) moves along with its words; one
          // whose passage left goes, and a pending one is resumed. Hiding and
          // showing it again on every scroll event made it flicker.
          // Only with a real pointer: a tap leaves :hover stuck on touch.
          function refreshHoverPreview(event) {
            // A long card scrolling in itself moves nothing.
            const scrolled = event?.target;
            if (scrolled?.nodeType === 1 && scrolled.closest(".insight-preview, .claim-popover")) return;
            refreshPinnedCard();
            const group = hoverGroup;
            if (!group || !canHoverPassages()) {
              hideHoverPreview();
              return;
            }
            requestAnimationFrame(function () {
              if (hoverGroup !== group) return;
              const targets = [...group.spans, ...group.controls.map(control => control.el), hoverCard].filter(Boolean);
              const held = targets.some(el => el.isConnected && el.matches(':hover, :focus-visible'));
              if (!held || !passageIsVisible(group)) {
                hideHoverPreview();
                return;
              }
              group.hover = true;
              const spans = placedSpans(group);
              if (hoverCard && !hoverCard.hidden && spans.length) placeCard(hoverCard, cardAnchor(spans), spans);
              else scheduleHoverPreview(group);
            });
          }
          window.addEventListener("scroll", refreshHoverPreview, true);
          window.addEventListener("resize", refreshHoverPreview);
          // Ein Klick nimmt die Vorschau weg, ausser er gilt ihrer Marke
          // selbst: dann haelt openCard sie an Ort und Stelle fest. Ein Link
          // oder Quellenchip im Satz nimmt sie mit. In der Karte entscheiden
          // ihre Knoepfe selbst.
          document.addEventListener("click", function (event) {
            const group = hoverGroup;
            const target = event.target;
            if (hoverCard && hoverCard.contains(target)) return;
            const own = group && [...group.spans, ...group.controls.map(control => control.el)]
              .some(el => el.contains(target));
            if (!own || target.closest?.("a, button:not(.claim-badge)")) hideHoverPreview();
          }, true);

          // --- Die Karte einer Marke ------------------------------------------
          // Seit 2026-10-23 (Max: "das muss perfekt sein") spricht jede Marke
          // dieselbe Sprache wie die Differences-Schublade: Behauptungen, die
          // sich gegenueberstehen, "vs" dazwischen, und unter jeder, wer sie
          // vertritt (Logos, ein oder zwei Namen, sonst die Anzahl). Keine
          // Quote "5/6 stuetzen das" an einem Streit, keine Namenslisten,
          // keine Etiketten, kein "Klicken fuer ...". Vorschau, festgehaltene
          // Karte und das Blatt auf dem Handy bauen denselben Inhalt. Bedienbar
          // (ctx.interactive) werden die Logos zu Wegen in die Antwort ihres
          // Modells, und die Fusszeile (cardActions) fuehrt in den Leser: zum
          // Unterschied (Resolve, Zitate, alle Unterschiede) und zu den
          // Antworten. Ihr Titel fuehrte vorher als Chevron dorthin, das sah
          // niemand (Max 2026-10-23). `ctx.close` schliesst die Karte vor dem
          // Weg (festgehalten: closeClaimPopover, Vorschau: leavePreviewFor).

          // Der Pin oben rechts (Max 2026-10-23): dass ein Klick die Karte
          // festhaelt, sieht man jetzt. In der Vorschau umrandet, ein Klick
          // heftet an; an der festgehaltenen Karte gefuellt, ein Klick loest
          // sie. Das Blatt auf dem Handy hat sein x statt des Pins.
          const PIN_ICON = '<svg class="cx-card-pin-icon" viewBox="0 0 24 24" aria-hidden="true">'
            + '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>'
            + '</svg>';

          function cardPin(pinned, act) {
            const pin = document.createElement("button");
            pin.type = "button";
            pin.className = "cx-card-pin";
            pin.innerHTML = PIN_ICON;
            pin.setAttribute("aria-pressed", pinned ? "true" : "false");
            pin.setAttribute("aria-label", pinned ? "Unpin" : "Pin");
            pin.title = pinned ? "Unpin" : "Pin";
            pin.addEventListener("click", function (event) {
              event.preventDefault();
              event.stopPropagation();
              act();
            });
            return pin;
          }

          function cardNode(tag, className, text) {
            const node = document.createElement(tag);
            node.className = className;
            if (text != null) node.textContent = text;
            return node;
          }

          // Ein Modell, wie Claims es nennen: als Name, in alten Daten als {model}.
          function cardModel(model) {
            return typeof model === "string" ? model : String(model?.model || model?.provider || "");
          }

          function cardNames(models) {
            return models.map(function (model) { return modelDisplayName(cardModel(model)); }).join(", ");
          }

          // Wer eine Seite vertritt: ein oder zwei Namen, ab drei die Anzahl
          // (die Namen tragen dann die Logos).
          function cardWho(models) {
            if (models.length > 2) return cardNode("span", "cx-card-who", models.length + " models");
            const names = cardNode("span", "cx-card-who", cardNames(models));
            names.setAttribute("data-i18n-skip", "");
            return names;
          }

          function cardLogos(models, ctx, quote) {
            const stack = cardNode("span", "cx-card-logos");
            models.map(cardModel).forEach(function (model) {
              const name = modelDisplayName(model);
              const opens = !!(ctx.interactive && ctx.navigation?.canOpen?.(model));
              const logo = cardNode(opens ? "button" : "span", "cx-card-logo");
              logo.appendChild(window.App.createModelMark?.(model)
                || cardNode("span", "model-mark-fallback", String(name).slice(0, 1).toUpperCase()));
              if (opens) {
                logo.type = "button";
                logo.title = "Open the full answer from " + name;
                logo.setAttribute("aria-label", "Open the full answer from " + name);
                logo.addEventListener("click", function () {
                  // The focus goes back to the mark first: the reader that
                  // opens hands it back there, not to a button of a closed card.
                  closeCard(ctx);
                  ctx.navigation.open(model, quote);
                });
              } else {
                logo.setAttribute("role", "img");
                logo.setAttribute("aria-label", name);
              }
              stack.appendChild(logo);
            });
            return stack;
          }

          // Eine Seite: die Behauptung als Satz, darunter wer sie vertritt.
          // `content.plain`: sichtbarer Text der Antwort (die strittigen
          // Worte), sonst Markdown aus Anker oder Zitat.
          function cardSide(content, models, ctx, options) {
            const side = cardNode("div", "cx-card-side");
            if (content && content.text) {
              const claim = cardNode("div", "cx-card-claim");
              if (content.plain) {
                claim.textContent = content.text;
                claim.setAttribute("data-i18n-skip", "");
              } else {
                renderInlineMarkdown(claim, content.text);
              }
              side.appendChild(claim);
            }
            const meta = cardNode("div", "cx-card-meta");
            if (models.length) meta.appendChild(cardLogos(models, ctx, options.quote || ""));
            // Anzahl und "In the answer" brechen nur gemeinsam um: auf dem
            // Handy stand nach fuenf Logos sonst ein einsamer Punkt am
            // Zeilenanfang.
            const words = cardNode("span", "cx-card-words");
            if (models.length) words.appendChild(cardWho(models));
            if (options.label) words.appendChild(cardNode("span", "cx-card-tag", options.label));
            if (words.firstChild) meta.appendChild(words);
            if (meta.firstChild) side.appendChild(meta);
            return side;
          }

          function cardVersus() {
            return cardNode("div", "cx-card-vs", "vs");
          }

          function closeCard(ctx) {
            (ctx.close || closeClaimPopover)();
          }

          function cardTitle(text) {
            const title = cardNode("div", "cx-card-title", text);
            title.setAttribute("data-i18n-skip", "");
            return title;
          }

          // Die Wege aus der Karte, mit Glyphe und Wort der Leiste unter der
          // Antwort (agent-review.js evidenceButton): wer sie dort kennt,
          // weiss, wohin sie fuehren. `differences`: der Unterschied dieser
          // Marke im Leser. `answers`: die erste Antwort, die sich oeffnen
          // laesst, zuerst die der Gegenseite, an ihrem Zitat.
          const CARD_ACTION_ICONS = {
            differences: "M12 20v-7M12 13 5 6M12 13l7-7M5 11V6h5M14 6h5v5",
            answers: "M4 4h12v10H8l-4 4V4ZM16 8h4v12l-4-4h-4"
          };

          function cardAction(section, label, run, ctx) {
            const button = cardNode("button", "cx-card-action");
            button.type = "button";
            button.dataset.section = section;
            button.innerHTML = '<svg class="cx-card-action-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="'
              + CARD_ACTION_ICONS[section] + '"/></svg>';
            button.appendChild(cardNode("span", "cx-card-action-label", label));
            button.addEventListener("click", function () {
              closeCard(ctx);
              run();
            });
            return button;
          }

          function cardActions(ctx, options) {
            if (!ctx.interactive) return null;
            const row = cardNode("div", "cx-card-actions");
            if (ctx.openInDrawer) {
              row.appendChild(cardAction("differences", options.differenceLabel || "Differences", ctx.openInDrawer, ctx));
            }
            const answer = (options.answers || []).find(function (item) {
              return ctx.navigation?.canOpen?.(cardModel(item.model));
            });
            if (answer) {
              row.appendChild(cardAction("answers", "Answers", function () {
                ctx.navigation.open(cardModel(answer.model), answer.quote || "");
              }, ctx));
            }
            return row.firstChild ? row : null;
          }

          function modelQuotes(sides) {
            const list = [];
            sides.forEach(function (side) {
              (side.models || []).forEach(function (model) { list.push({ model: model, quote: side.quote || "" }); });
            });
            return list;
          }

          // Ohne sichtbaren Titel: der Name der Karte fuer Screenreader.
          function cardHeading(text) {
            return cardNode("span", "visually-hidden cx-card-heading", text);
          }

          function cardNote(text) {
            return cardNode("p", "cx-card-note", text);
          }

          // Schweigen bleibt sichtbar, aber leise: weder Zustimmung noch Widerspruch.
          function cardAside(models) {
            const aside = cardNode("div", "cx-card-aside");
            const names = cardNode("span", "cx-card-aside-names", cardNames(models));
            names.setAttribute("data-i18n-skip", "");
            aside.append(cardNode("span", "cx-card-aside-label", "Not addressed"), names);
            return aside;
          }

          function appendClaimSupport(target, claim) {
            if (claimCoverage(claim) === "thin") {
              target.textContent = "Too few models addressed this";
              return;
            }
            const ratio = document.createElement("strong");
            ratio.className = "claim-support-ratio";
            ratio.textContent = claim.agree.length + "/" + (claim.agree.length + claim.dissent.length);
            target.append(ratio, document.createTextNode(" models that addressed this support it"));
          }

          // Die Seite der Antwort: die strittigen Worte, wenn der Satz genau
          // eine Stelle traegt, sonst die ganze Aussage.
          function claimAnswerSide(claim, spans) {
            const spots = [];
            (spans || []).forEach(function (span) {
              span.querySelectorAll?.(".cx-spot").forEach(function (spot) {
                const text = spot.textContent.trim();
                if (text && !spots.includes(text)) spots.push(text);
              });
            });
            return spots.length === 1 ? { text: spots[0], plain: true } : { text: claim.anchor };
          }

          // Die Gegenseiten: gleiche Zitate sind eine Seite, jedes Modell
          // steht nur einmal.
          function dissentSides(claim) {
            const sides = [];
            claim.dissent.forEach(function (item) {
              const quote = item && typeof item.quote === "string" ? item.quote.trim() : "";
              const key = claimKey(quote);
              const same = sides.find(function (side) { return side.key === key; });
              if (same) {
                if (!same.models.includes(item.model)) same.models.push(item.model);
              } else {
                sides.push({ key: key, quote: quote, models: [item.model] });
              }
            });
            return sides;
          }

          // Eine gepruefte Aussage. Bestritten: die Seite der Antwort gegen die
          // Zitate der Abweichler. Unbestritten oder duenn belegt: wie viele
          // sie stuetzen, mit dem Satz, ohne den die Quote missverstanden wird.
          function claimCard(claim, modelsCompared, ctx) {
            const card = cardNode("div", "cx-card");
            const total = claim.agree.length + claim.dissent.length;
            if (claim.dissent.length) {
              card.appendChild(cardHeading(claim.agree.length + " of " + total + " models support this"));
              card.appendChild(cardSide(claimAnswerSide(claim, ctx.spans), claim.agree, ctx,
                { label: ctx.sideLabel || "In the answer" }));
              dissentSides(claim).forEach(function (side) {
                card.append(cardVersus(), cardSide(side.quote ? { text: side.quote } : null, side.models, ctx,
                  { quote: side.quote }));
              });
            } else {
              const title = cardNode("div", "cx-card-title");
              appendClaimSupport(title, claim);
              card.appendChild(title);
              if (claim.agree.length) {
                const meta = cardNode("div", "cx-card-meta");
                meta.append(cardLogos(claim.agree, ctx, ""), cardWho(claim.agree));
                card.appendChild(meta);
              }
            }
            const notAddressed = modelsNotAddressingClaim(claim, modelsCompared);
            if (notAddressed.length) card.appendChild(cardAside(notAddressed));
            if (!claim.dissent.length) {
              // "6/6" ist eine Uebereinstimmung zwischen Modellen, kein
              // Wahrheitsbeweis; duenn belegt heisst nur: nicht geprueft.
              card.appendChild(cardNote(claimCoverage(claim) === "thin"
                ? "Too little was said about this to compare. That is not evidence against it — it just was not checked."
                : "Models agreeing is not proof. They can share the same source or the same blind spot."));
            }
            const actions = cardActions(ctx, {
              answers: modelQuotes(dissentSides(claim)).concat(modelQuotes([{ models: claim.agree }]))
            });
            if (actions) card.appendChild(actions);
            return card;
          }

          // Ein Unterschied aus der Differences-Analyse, wie seine Karte in der
          // Schublade: das Thema als Titel, die Seiten der Antwort vorn, "vs"
          // nur bei einem Widerspruch.
          function differenceCard(diff, ctx) {
            const card = cardNode("div", "cx-card");
            const readable = readableDifference(diff, modelDisplayName);
            const isVersus = diff.type === "contradiction" && readable.positions.length > 1;
            if (readable.narrative && isVersus) card.appendChild(cardHeading(differenceKind(diff)));
            else card.appendChild(cardTitle(readable.claim));
            const positions = readable.positions.slice().sort(function (a, b) {
              return (b.in_answer === true) - (a.in_answer === true);
            });
            positions.forEach(function (pos, index) {
              if (isVersus && index) card.appendChild(cardVersus());
              const text = pos.stance || pos.quote;
              card.appendChild(cardSide(text ? { text: text } : null, pos.models, ctx, {
                quote: pos.quote || "",
                label: pos.in_answer === true ? "In the answer" : ""
              }));
            });
            const actions = cardActions(ctx, {
              differenceLabel: diff.type === "contradiction" ? "Contradictions" : "Differences",
              answers: modelQuotes(positions.filter(function (pos) { return pos.in_answer !== true; }))
                .concat(modelQuotes(positions.filter(function (pos) { return pos.in_answer === true; })))
            });
            if (actions) card.appendChild(actions);
            return card;
          }

          // A provisional mark (agent-review.js preview) says only that its
          // sentence was compared, never how it came out: the verdict and its
          // colour arrive together with the finished check.
          function provisionalCard(modelsCompared) {
            const card = cardNode("div", "cx-card");
            const count = Array.isArray(modelsCompared) ? modelsCompared.length : 0;
            card.append(
              cardNode("div", "cx-card-title", count
                ? (count === 1 ? "Compared with 1 model answer" : "Compared with " + count + " model answers")
                : "Compared with the model answers"),
              cardNote("The result appears once the whole answer is checked"));
            return card;
          }

          // Haengt das Steuerelement hinter die Passage und verbindet beide.
          function attachControl(result, control, activate, preview) {
            insertAfterMark(result, control);
            const spans = result.spans;
            if (!spans || !spans.length) return null;
            const group = passageGroup(spans);
            const entry = { el: control, activate: activate, preview: preview };
            group.controls.push(entry);
            // Die Karte eines Badges zeigt auf die strittigen Worte seines Satzes.
            control.cxSpans = spans;
            control.addEventListener("mouseenter", function () { if (canHoverPassages()) setPassageHover(group, true); });
            control.addEventListener("mouseleave", function () { setPassageHover(group, false); });
            return entry;
          }

          // Dieselbe Kopplung ohne eigenes Element: die angestrichene Passage
          // IST das Steuerelement. Seit die Punkte weg sind (2026-08-15) haengt
          // hier die gesamte Bedienbarkeit einer Differenz - ohne role/tabindex
          // waere sie fuer Tastatur und Screenreader unerreichbar. Der erste
          // Span traegt die Semantik; ein Satz, der ueber einen Zeilenumbruch
          // in mehrere Spans zerfaellt, bekommt trotzdem nur EINEN Tabstopp.
          function attachPassageControl(result, label, activate, preview) {
            const spans = result.spans;
            if (!spans || !spans.length) return null;
            const group = passageGroup(spans);
            const host = spans[0];
            host.setAttribute("role", "button");
            host.setAttribute("tabindex", "0");
            host.setAttribute("aria-label", passageLabel(spans, label));
            if (!host.dataset.cxKeyboard) {
              host.dataset.cxKeyboard = "1";
              host.addEventListener("keydown", function (event) {
                if (!passageIsVisible(group)) return;
                if (event.key !== "Enter" && event.key !== " " && event.key !== "Spacebar") return;
                event.preventDefault();
                const target = activeControl(group);
                if (target) target.activate(event);
              });
              host.addEventListener("focus", function () { focusPassage(group, host); });
              host.addEventListener("blur", function () { setPassageHover(group, false); });
            }
            const entry = { el: host, activate: activate, preview: preview, isPassage: true };
            group.controls.push(entry);
            return entry;
          }

          // Das unterlegene Control tritt zurueck, bleibt aber fuer Vorschau
          // und Zaehlung im Group-Objekt. Bei einer Passage heisst
          // "zuruecktreten" auch: den Tabstopp abgeben, sonst haette der Satz
          // zwei Fokusziele (Passage und Badge) fuer dieselbe Aussage.
          function suppressControl(entry) {
            if (!entry) return;
            entry.suppressed = true;
            if (entry.isPassage) {
              entry.el.removeAttribute("role");
              entry.el.removeAttribute("tabindex");
              entry.el.removeAttribute("aria-label");
              return;
            }
            entry.el.hidden = true;
            entry.el.setAttribute("aria-hidden", "true");
            entry.el.tabIndex = -1;
          }

          // Nur die Vorschau, ohne Klick und ohne Tabstopp: fuer vorlaeufige
          // Marken und fuer die Saetze einer geprueften Nachricht, deren Klick
          // und Tastatur ihrer eigenen Karte gehoeren (passage-check.js).
          function attachPreviewOnly(spans, preview, focusable) {
            if (!spans || !spans.length || spans[0].cxGroup) return null;
            const group = passageGroup(spans, false);
            const entry = { el: spans[0], activate: function () {}, preview: preview, isPassage: true, pinnable: !!focusable };
            group.controls.push(entry);
            if (focusable) {
              spans[0].addEventListener("focus", function () { focusPassage(group, spans[0]); });
              spans[0].addEventListener("blur", function () { setPassageHover(group, false); });
            }
            return entry;
          }

          // Die Hover-Karte eines geprueften Satzes der Nachricht des Nutzers:
          // dieselbe Vorschau wie ein Satz der Antwort; ein Klick oeffnet
          // weiter die Karte (App.claimPopover.open), die die Vorschau ersetzt.
          function attachClaimPreview(span, claim, modelsCompared, options) {
            if (!span || !claim) return;
            attachPreviewOnly([span], function (ctx) {
              return claimCard(claim, modelsCompared, Object.assign({
                spans: [span], sideLabel: options?.sideLabel, navigation: options?.navigation
              }, ctx));
            }, true);
          }

          function renderInlineMarkers(claims, differences, modelsCompared, options) {
            options = options || {};
            const body = options.body || window.App.consensusBodyEl();
            const fallbackBox = options.fallbackBox || $("consensusClaimsFallback");
            const answerNavigation = options.answerNavigation || LIVE_ANSWER_NAVIGATION;
            // Ein archivierter Turn hat seine eigenen Karten; der Live-Fuss
            // gehoert bereits dem naechsten Lauf.
            const focusDifference = options.focusDifference || focusDifferenceCard;
            if (!body || !fallbackBox) return;
            // Neu markiert: eine offene Vorschau dieses Textes gehoert zu Spans,
            // die es gleich nicht mehr gibt (oder schon nicht mehr gibt).
            hidePreviewWithin(body);

            // Pro Blockelement eine eigene Liste bereits markierter Bereiche:
            // die flachen Offsets gelten nur innerhalb ihres Blocks.
            const markedByBlock = new Map();
            function marksFor(block) {
              if (!markedByBlock.has(block)) markedByBlock.set(block, []);
              return markedByBlock.get(block);
            }
            // markSentence braucht die Liste, bevor der Block bekannt ist -
            // deshalb eine gemeinsame Liste je Aufruf und Zuordnung danach.
            function mark(anchor, severityClass, occurrence) {
              const probe = locateAnchor(body, anchor, occurrence);
              if (!probe) return null;
              return markSentence(
                body, anchor, severityClass, marksFor(probe.block), occurrence
              );
            }

            // Vorlaeufig (agent-review.js preview, seit 2026-10-21 neutral):
            // jeder schon verglichene Satz traegt dieselbe leise Marke, ohne
            // Farbe, Quote, Stelle oder Liste und mit einer Vorschau ohne
            // Urteil. Was die Pruefung ergibt, kommt erst mit der fertigen
            // Pruefung (Max 2026-10-21: erst ein gelber Satz, dann keiner, dann
            // ein ganz anderer roter).
            if (options.provisional) {
              let anchored = 0;
              claims.forEach(function (claim) {
                const result = mark(claim.anchor, "is-provisional", claim.anchor_occurrence);
                if (!result) return;
                anchored += 1;
                attachPreviewOnly(result.spans, function () { return provisionalCard(modelsCompared); });
              });
              applyConsensusMarkerVisibility(storedConsensusMarkersVisible(), false, body, fallbackBox);
              return { claims_anchored: anchored, claims_unanchored: claims.length - anchored };
            }

            // Wenn Claim und Difference denselben Satz meinen, steht dort nur
            // EIN sichtbares Signal — welches, entscheidet die Schwere:
            //
            // - WIDERSPRUCH: die Passage gewinnt, das Claim-Badge entfaellt.
            //   Seit die Claims jeden pruefbaren Satz abdecken (Satz-Index,
            //   2026-08-07), traegt ein strittiger Satz fast IMMER auch ein
            //   Claim-Badge. Mit der alten Regel (Badge gewinnt) verschwand
            //   damit praktisch jeder Widerspruch aus dem Text: der
            //   strittige Satz sah aus wie jeder andere, und der Klick darauf
            //   oeffnete "4 of 6 models agree" statt der Widerspruchs-Karte.
            //   Genau das ist der Kern des Produkts — es darf nicht als
            //   Zustimmungsquote getarnt werden.
            // - EMPHASIS: das Badge gewinnt wie bisher; eine andere Gewichtung
            //   ist die schwaechere Aussage als die Stuetzungsquote.
            //
            // Das unterlegene Control bleibt als suppressed im Group-Objekt,
            // damit Hover-Vorschau und Zaehlung es weiterhin kennen.
            const differenceControls = [];

            // Trefferquote der Ankersuche: nur so laesst sich belegen, ob eine
            // Aenderung an Ankern oder Suche die Abdeckung wirklich hebt -
            // statt sie zu schaetzen. Fliesst in app_consensus_insights_rendered.
            let diffAnchorMisses = 0;

            // 1. Widersprüche zuerst: sie tragen die stärkere Markierung.
            differences.forEach(function (diff, index) {
              if (!diff.consensus_anchor) return;
              const isMajor = diff.type === "contradiction" && diff.severity === "major";
              const result = mark(
                diff.consensus_anchor,
                isMajor ? "is-major" : "is-minor",
                diff.anchor_occurrence
              );
              if (!result) {
                diffAnchorMisses += 1;
                return;
              }
              const control = attachPassageControl(
                result,
                diffMarkerLabel(diff),
                function () {
                  openDifferencePopover(diff, result.spans, answerNavigation, function () { focusDifference(index); });
                },
                function (ctx) {
                  return differenceCard(diff, Object.assign({
                    navigation: answerNavigation,
                    openInDrawer: function () { focusDifference(index); }
                  }, ctx));
                }
              );
              if (diff.type === "contradiction" && result.spans[0]?.cxGroup) {
                result.spans[0].cxGroup.hasContradiction = true;
              }
              differenceControls.push({
                spans: result.spans,
                control: control,
                isContradiction: diff.type === "contradiction"
              });
            });

            // 2. Claims, in drei Stufen (die vierte, der Widerspruch, ist oben
            //    schon gesetzt):
            //      is-split      geteilte Zustimmung — Bernstein, eine Stufe
            //                    leiser als der Widerspruch
            //      is-unanimous  gestuetzt — gruen, das Badge traegt die Quote
            //      is-thin       zu duenn belegt — grau, damit ein Satz, den
            //                    kaum ein Modell behandelt hat, sichtbar bleibt
            //                    statt wie ungeprueft auszusehen
            const unanchored = [];
            const claimControls = [];
            // Satz-Spans -> bestrittene Worte. Ein Widerspruch und ein Claim
            // auf demselben Satz teilen sich dieselben Spans (markSentence).
            const spotTargets = new Map();
            function collectSpotTargets(spans, claim) {
              const targets = claim.dissent
                .map(function (item) { return item && typeof item.target === "string" ? item.target.trim() : ""; })
                .filter(Boolean);
              if (!targets.length) return;
              if (!spotTargets.has(spans)) spotTargets.set(spans, { spans: spans, targets: [] });
              spotTargets.get(spans).targets.push(...targets);
            }
            const coverageCounts = { supported: 0, split: 0, thin: 0 };
            claims.forEach(function (claim, claimIndex) {
              const coverage = claimCoverage(claim);
              // Steht der Satz in der Liste (listedClaim), fuehrt seine Karte dorthin.
              const openInDrawer = listedClaim(claim, differences)
                ? function () { focusDifference("c" + claimIndex); } : null;
              coverageCounts[coverage] = (coverageCounts[coverage] || 0) + 1;
              const result = mark(
                claim.anchor,
                coverage === "split" ? "is-split"
                  : coverage === "thin" ? "is-thin" : "is-unanimous",
                claim.anchor_occurrence
              );
              if (!result) {
                unanchored.push(claim);
                return;
              }
              collectSpotTargets(result.spans, claim);
              const overlappingDifference = differenceControls.find(function (entry) {
                return entry.spans === result.spans;
              });
              // Auf einem strittigen Satz behaelt der Widerspruch das Wort.
              // Der Satz ist bereits markiert (markSentence hat die staerkere
              // is-major/is-minor-Linie gesetzt), er bekommt hier nur kein
              // zweites, schwaecher klingendes Steuerelement daneben.
              if (overlappingDifference && overlappingDifference.isContradiction) return;

              const badge = makeBadge(claim, modelsCompared, answerNavigation, { openInDrawer: openInDrawer });
              const total = claim.agree.length + claim.dissent.length;
              const support = total ? claim.agree.length / total : 1;
              const existingClaim = claimControls.find(function (entry) {
                return entry.spans === result.spans;
              });

              // Mehrere gepruefte Claims koennen im selben Satz liegen. Zwei
              // Quoten hinter demselben Satz waeren wieder genau die
              // Ueberladung, die diese Mikro-Marke vermeiden soll. Sichtbar
              // bleibt deshalb die konservative Satzquote: der am wenigsten
              // gestuetzte Claim.
              if (existingClaim && support >= existingClaim.support) return;
              if (existingClaim) {
                existingClaim.badge.remove();
                const group = result.spans[0]?.cxGroup;
                if (group) {
                  group.controls = group.controls.filter(function (control) {
                    return control.el !== existingClaim.badge;
                  });
                }
                existingClaim.badge = badge;
                existingClaim.support = support;
              } else {
                claimControls.push({
                  spans: result.spans,
                  badge: badge,
                  support: support
                });
              }
              // Nur noch Emphasis-Marken treten hinter das Badge zurueck.
              if (overlappingDifference) suppressControl(overlappingDifference.control);
              attachControl(result, badge, function () {
                const anchor = document.body.classList.contains("claim-counts-visible") ? badge : result.spans[0];
                openClaimPopover(claim, anchor, modelsCompared, answerNavigation, { spans: result.spans, openInDrawer: openInDrawer });
              }, function (ctx) {
                return claimCard(claim, modelsCompared, Object.assign({
                  spans: result.spans, navigation: answerNavigation, openInDrawer: openInDrawer
                }, ctx));
              });
            });

            // 3. Die Stelle des Streits: in einem bestrittenen Satz traegt nur
            //    sie die Farbe (wrapSpots).
            spotTargets.forEach(function (entry) { wrapSpots(entry.spans, entry.targets); });

            if (unanchored.length) {
              // Der Anker ist eine woertliche Kopie des Konsenstextes und
              // traegt damit dessen Quellentags. Im Fliesstext macht
              // linkifySourceTags daraus die hochgestellte Fussnote - hier
              // stand bis dahin die rohe Klammer "[S4]" im Satz.
              const sources = Array.isArray(options.sources)
                ? options.sources
                : (Array.isArray(window.currentEvidenceSources) ? window.currentEvidenceSources : []);
              fallbackBox.innerHTML = "";
              const title = document.createElement("div");
              title.className = "claims-fallback-title";
              title.textContent = "Key claims";
              fallbackBox.appendChild(title);
              unanchored.forEach(function (claim) {
                const row = document.createElement("div");
                row.className = "claims-fallback-row";
                row.dataset.coverage = claimCoverage(claim);
                const text = document.createElement("span");
                text.className = "claims-fallback-text";
                renderInlineMarkdown(text, claim.anchor);
                row.append(text, makeBadge(claim, modelsCompared, answerNavigation));
                fallbackBox.appendChild(row);
                // Erst nach dem Einhaengen: die Nummernform erkennt
                // linkifySourceTags an den Vorfahren der Zeile.
                if (sources.length) window.linkifySourceTags?.(text, sources);
              });
              fallbackBox.hidden = false;
            }

            // Legende nur, wenn wirklich etwas markiert wurde. Sie verhindert,
            // dass unmarkierter Text als geprueft-und-bestaetigt gelesen wird.
            if (!options.stored) {
              // Die Provenance-Zeile zaehlt die strittigen Stellen aus genau
              // diesen Markern. Sie wird beim Laufende zuerst ohne sie gerendert
              // (die Marker entstehen erst hier) und holt die Zahl jetzt nach.
              window.App?.consensusPipeline?.renderProvenance?.();
            }

            // History-Turns werden vor dem Einfuegen in den DOM aufgebaut.
            // Filter und Passage-Tabstopps deshalb direkt auf ihren Containern
            // anwenden, damit die erste Darstellung bereits zur Auswahl passt.
            applyConsensusMarkerVisibility(storedConsensusMarkersVisible(), false, body, fallbackBox);

            return {
              claims_anchored: claims.length - unanchored.length,
              claims_unanchored: unanchored.length,
              diffs_unanchored: diffAnchorMisses,
              claims_supported: coverageCounts.supported,
              claims_split: coverageCounts.split,
              claims_thin: coverageCounts.thin
            };
          }

          // Gespeicherte Chat-Turns besitzen eigene Antwortcontainer und keine
          // globalen Live-IDs. Claims werden deshalb containerlokal erneut
          // verankert; Hover und Detaildialog bleiben genauso erreichbar wie
          // beim aktuell sichtbaren Consensus.
          function renderStoredConsensusClaims(body, data, fallbackBox, sources, options = {}) {
            if (!body || !data || typeof data !== "object") return false;
            const claims = (Array.isArray(data.claims) ? data.claims : [])
              .filter(c => c && c.anchor && Array.isArray(c.agree) && Array.isArray(c.dissent));
            const modelsCompared = Array.isArray(data.models_compared)
              ? data.models_compared : [];
            // Die Widersprueche gehoeren MIT in den Verlauf: ohne sie fiel ein
            // strittiger Satz beim naechsten Turn auf sein Claim-Badge zurueck
            // und las sich als "1 of 6 models support this" (bernstein) statt
            // als roter Widerspruch — dieselbe Antwort, entschaerft.
            const differences = (Array.isArray(data.differences) ? data.differences : [])
              .filter(d => d && d.claim && Array.isArray(d.positions) && d.positions.length);
            renderInlineMarkers(claims, differences, modelsCompared, {
              body: body,
              fallbackBox: fallbackBox,
              stored: true,
              focusDifference: options.focusDifference || storedDifferenceFocus(body),
              // Ein archivierter Turn hat seine eigenen Quellen; die globale
              // Liste gehoert bereits dem naechsten Lauf.
              sources: Array.isArray(sources) ? sources : [],
              answerNavigation: options.answerNavigation || storedAnswerNavigation(body),
              provisional: options.provisional === true
            });
            return claims.length > 0;
          }

          // --- Resolve-Runde ---------------------------------------------------
          // Konfrontiert die dissentierenden Modelle eines Widerspruchs gezielt
          // mit der Gegenposition (POST /resolve). Pro-Feature: Free-Nutzer
          // sehen den Button als Teaser (öffnet das Pro-Modal). Ergebnis wird
          // in der Karte gerendert, am diff-Objekt gemerkt und über das
          // Consensus-Bookmark persistiert.
          const RESOLVE_STATUS = {
            resolved: { cls: "is-resolved", label: "Resolved" },
            standoff: { cls: "is-standoff", label: "Dissent confirmed" },
            mutual_revision: { cls: "is-mixed", label: "Still unclear" }
          };

          function resolveOutcomeSummary(outcome, results) {
            const revised = results.filter(r => r.decision === "revise").map(r => modelDisplayName(r.model));
            const maintained = results.filter(r => r.decision === "maintain").map(r => modelDisplayName(r.model));
            switch (outcome) {
              case "resolved":
                return {
                  cls: "is-resolved",
                  text: "Resolved: " + revised.join(", ") + " revised after seeing the counter-position; "
                    + maintained.join(", ") + " confirmed."
                };
              case "standoff":
                return { cls: "is-standoff", text: "Confirmed dissent: every model maintains its position after re-examination." };
              case "mutual_revision":
                return { cls: "is-mixed", text: "All models revised their position. The point stays unclear; verify independently." };
              default:
                return { cls: "is-error", text: "The resolve round did not return a usable result. Please try again." };
            }
          }

          // Down-Chevron fuer den Aufklapp-Pfeil (rotiert per CSS bei [open]).
          const RESOLVE_CHEVRON =
            '<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true" fill="none" '
            + 'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            + '<path d="M2.5 4.5 6 8l3.5-3.5"/></svg>';

          function decisionLabel(decision) {
            return decision === "maintain" ? "maintains"
              : (decision === "revise" ? "revised" : "no result");
          }

          function renderResolveResult(resultBox, data) {
            resultBox.innerHTML = "";
            const summary = resolveOutcomeSummary(data.outcome, Array.isArray(data.results) ? data.results : []);
            const badge = document.createElement("div");
            badge.className = "resolve-outcome " + summary.cls;
            badge.textContent = summary.text;
            resultBox.appendChild(badge);

            (Array.isArray(data.results) ? data.results : []).forEach(function (r) {
              // Die im Resolve neu gegebene Antwort (position + reason) steckt
              // platzsparend hinter einem Aufklapp-Pfeil. Ohne Antwort (Fehler/
              // kein Ergebnis) bleibt die Zeile eine einfache, nicht klappbare Box.
              // Bewusst kein <details>/<summary>: das native Collapse ist auf
              // dieser Seite global ausgehebelt; wir klappen per Klasse selbst.
              const hasDetail = !!(r.position || r.reason);
              const row = document.createElement("div");
              row.className = "resolve-model-row" + (hasDetail ? " is-collapsible" : "");

              const head = document.createElement(hasDetail ? "button" : "div");
              head.className = "resolve-model-head" + (hasDetail ? " resolve-model-toggle" : "");
              if (hasDetail) {
                head.type = "button";
                head.setAttribute("aria-expanded", "false");
                head.title = "Show this model’s revised answer";
              }

              const name = document.createElement("span");
              name.className = "resolve-model-name";
              name.textContent = modelDisplayName(r.model);
              const decision = document.createElement("span");
              decision.className = "resolve-decision is-" + (r.decision || "error");
              decision.textContent = decisionLabel(r.decision);
              head.append(name, decision);

              if (!hasDetail) {
                row.appendChild(head);
                resultBox.appendChild(row);
                return;
              }

              const disclosure = document.createElement("span");
              disclosure.className = "resolve-disclosure";
              disclosure.setAttribute("aria-hidden", "true");
              disclosure.innerHTML = RESOLVE_CHEVRON;
              head.appendChild(disclosure);

              const detail = document.createElement("div");
              detail.className = "resolve-model-detail";
              if (r.position) {
                const pos = document.createElement("div");
                pos.className = "resolve-position";
                pos.textContent = r.position;
                detail.appendChild(pos);
              }
              if (r.reason) {
                const reason = document.createElement("div");
                reason.className = "resolve-reason";
                reason.textContent = r.reason;
                detail.appendChild(reason);
              }

              head.addEventListener("click", function () {
                const open = row.classList.toggle("is-open");
                head.setAttribute("aria-expanded", open ? "true" : "false");
              });

              row.append(head, detail);
              resultBox.appendChild(row);
            });

            // Transparenz: den tatsaechlich gestellten Prompt hinter einem
            // Toggle zeigen. Nur in der Live-Session verfuegbar (das Feld wird
            // nicht ins Bookmark/Share persistiert, s. runResolveRound).
            const withPrompt = (Array.isArray(data.results) ? data.results : []).filter(function (r) { return r.prompt; });
            if (withPrompt.length) {
              const promptWrap = document.createElement("div");
              promptWrap.className = "resolve-prompt";
              const toggle = document.createElement("button");
              toggle.type = "button";
              toggle.className = "resolve-prompt-toggle";
              toggle.setAttribute("aria-expanded", "false");
              toggle.innerHTML = RESOLVE_CHEVRON + "<span>What the models were asked</span>";
              const body = document.createElement("div");
              body.className = "resolve-prompt-body";
              body.hidden = true;
              withPrompt.forEach(function (r) {
                const item = document.createElement("div");
                item.className = "resolve-prompt-item";
                const modelHead = document.createElement("div");
                modelHead.className = "resolve-prompt-model";
                modelHead.textContent = modelDisplayName(r.model);
                const text = document.createElement("pre");
                text.className = "resolve-prompt-text";
                text.textContent = r.prompt;
                item.append(modelHead, text);
                body.appendChild(item);
              });
              toggle.addEventListener("click", function () {
                const open = body.hidden;
                body.hidden = !open;
                promptWrap.classList.toggle("is-open", open);
                toggle.setAttribute("aria-expanded", open ? "true" : "false");
              });
              promptWrap.append(toggle, body);
              resultBox.appendChild(promptWrap);
            }
            resultBox.hidden = false;
          }

          // Karte sichtbar als "gelöst/bestätigt/unklar" kennzeichnen: Status-
          // Chip in einer Zeile über dem Thema plus Karten-Klasse für den
          // Farbakzent. Die Zeile entsteht erst mit dem Ergebnis.
          function markCardResolved(card, outcome) {
            const status = RESOLVE_STATUS[outcome];
            if (!card || !status) return;
            card.classList.add("has-resolution", "resolution-" + status.cls.slice(3));
            let tagRow = card.querySelector(".diff-card-tags");
            const summary = card.querySelector(":scope > .diff-card-summary");
            if (!tagRow && summary) {
              tagRow = document.createElement("span");
              tagRow.className = "diff-card-tags";
              summary.insertBefore(tagRow, summary.querySelector(".diff-card-claim"));
            }
            if (!tagRow || tagRow.querySelector(".diff-resolved-tag")) return;
            const chip = document.createElement("span");
            chip.className = "diff-resolved-tag " + status.cls;
            chip.textContent = status.label;
            tagRow.appendChild(chip);
          }

          // Resolve is bound to one immutable bookmark revision before its
          // first await. The server persists only its own model result and
          // rechecks that revision inside the bookmark transaction.
          function resolutionBindingIsWritable(binding) {
            if (!binding?.bookmarkId) return false;
            if (window.App.bookmarkUi?.canWrite?.(binding.bookmarkId, binding.auth?.uid) === false) {
              return false;
            }
            const registry = window.App.runRegistry;
            if (!registry) return true;
            const owner = binding.runId ? registry.get?.(binding.runId) : null;
            if (binding.runId && (!owner || owner.bookmark?.deleted === true)) return false;
            const ownerCreatedAt = Number(binding.ownerCreatedAt || owner?.createdAt || 0);
            const boundary = ownerCreatedAt || Number(binding.boundAt || 0);
            // A follow-up created from the same bookmark is a newer resource
            // mutation. A late Resolve round from the predecessor may still be
            // shown in that predecessor's view, but must never roll persistence
            // back to its older chat/turn snapshot.
            return !(registry.list?.() || []).some(function (context) {
              return context.runId !== binding.runId
                && context.bookmark?.id === binding.bookmarkId
                && context.bookmark?.deleted !== true
                && Number(context.createdAt || 0) > boundary;
            });
          }

          function showResolveProTeaser() {
            window.trackUmamiEvent?.("app_resolve_pro_teaser_click");
            const shown = window.App?.showProFeatureModal?.("Resolve");
            if (!shown) {
              window.App?.showPopup?.("Resolve is not available on your account yet. You can still review the differences and model answers.");
            }
          }

          async function runResolveRound(diff, button, resultBox) {
            if (!window.auth?.currentUser) {
              window.App?.askToLogIn?.("Log in to resolve this disagreement.", { trigger: button, source: "resolve" });
              return;
            }
            // Bind everything before the first await. A different run or
            // bookmark may become visible while /resolve is still in flight.
            const boundContext = window.App.runRegistry?.visible?.() || null;
            const boundPayload = boundContext?.consensus?.bookmarkPayload
              || window.lastConsensusBookmarkPayload;
            const boundUser = boundContext?.auth?.user || window.auth.currentUser;
            const preparedShareContext = window.currentBookmarkShareResultContext;
            const boundConversation = boundPayload?.conversation || {};
            const boundBookmarkId = boundContext?.bookmark?.id
              || boundPayload?.conversation?.bookmarkId
              || window.App.runRegistry?.getSelectedConversationBasis?.()?.bookmarkId
              || null;
            const syntheticBookmark = {
              query: boundContext?.question || boundPayload?.question || "",
              chat_id: boundConversation.chatId || boundContext?.completedBasis?.chatId || "",
              turn_id: boundConversation.turnId || boundContext?.completedBasis?.turnId || "",
              share_result_id: boundPayload?.previousQuestion
                ? ""
                : (boundPayload?.resultId || boundContext?.consensus?.resultId || ""),
              responses: {
                consensus: boundContext?.consensus?.text || boundPayload?.consensusText || "",
                differences_data: boundPayload?.differencesData
                  || boundContext?.consensus?.differencesData
                  || null
              }
            };
            const binding = {
              runId: boundContext?.runId || null,
              bookmarkId: boundBookmarkId,
              payload: boundPayload,
              auth: boundContext?.auth || {
                user: boundUser,
                uid: boundUser?.uid || null,
                generation: window.App.authState?.generation
              },
              question: String(boundContext?.question || boundPayload?.question || "").trim(),
              useOwnKeys: boundContext?.config?.useOwnKeys
                ?? ($("useOwnKeysSwitch")?.checked === true),
              credentials: boundContext?.credentials
                ? Object.assign({}, boundContext.credentials)
                : Object.fromEntries(
                    ["openrouterKey"]
                      .map(function (key) { return [key, localStorage.getItem(key) || ""]; })
                  ),
              boundAt: Date.now(),
              ownerCreatedAt: Number(boundContext?.createdAt || 0),
              // A live run receives the exact, server-sanitized revision from
              // its queued consensus save. A prepared saved-bookmark view is
              // already bound to its own exact version. Synthetic parts are a
              // fail-safe fallback and can only fail the server-side guard.
              versionParts: Array.isArray(boundContext?.persistence?.consensusVersionParts)
                ? boundContext.persistence.consensusVersionParts.slice()
                : (!boundContext && preparedShareContext?.bookmarkId === boundBookmarkId
                    && Array.isArray(preparedShareContext.versionParts)
                  ? preparedShareContext.versionParts.slice()
                  : null),
              syntheticBookmark: syntheticBookmark
            };
            const actionController = new AbortController();
            let registryAction = null;
            try {
              registryAction = window.App.runRegistry?.beginAction?.({
                key: binding.bookmarkId
                  ? "resolve"
                  : `resolve:${JSON.stringify([diff.claim, diff.positions])}`,
                ownerRunId: binding.runId,
                bookmarkId: binding.bookmarkId,
                auth: binding.auth,
                controller: actionController
              }) || null;
            } catch (error) {
              window.App?.showPopup?.(window.App.userError(error, { fallback: "This resolve round can’t start yet." }));
              return;
            }
            const finishRegistryAction = function () {
              if (registryAction) {
                window.App.runRegistry?.finishAction?.(registryAction.actionId);
                registryAction = null;
              }
            };
            const authIsCurrent = function () {
              if (boundContext) return window.App.runRegistry?.isAuthCurrent?.(boundContext) === true;
              return window.auth?.currentUser === boundUser
                && window.auth?.currentUser?.uid === binding.auth.uid
                && window.App.authState?.generation === binding.auth.generation;
            };
            const viewStillOwnsResult = function () {
              if (binding.runId) return window.App.runRegistry?.isVisible?.(binding.runId) === true;
              const basis = window.App.runRegistry?.getSelectedConversationBasis?.();
              return !window.App.runRegistry?.visible?.()
                && Boolean(binding.bookmarkId)
                && basis?.bookmarkId === binding.bookmarkId;
            };
            let idToken = null;
            let expectedBookmarkVersion = "";
            try {
              [idToken] = await Promise.all([
                boundUser.getIdToken(),
                Promise.resolve(boundContext?.persistence?.consensusPromise).catch(() => undefined)
              ]);
              if (Array.isArray(boundContext?.persistence?.consensusVersionParts)) {
                binding.versionParts = boundContext.persistence.consensusVersionParts.slice();
              }
              if (!Array.isArray(binding.versionParts)) {
                binding.versionParts = window.App.bookmarkUi?.versionParts?.(binding.syntheticBookmark)
                  || [];
              }
              expectedBookmarkVersion = resolutionBindingIsWritable(binding)
                ? await window.App.bookmarkUi?.versionForParts?.(binding.versionParts)
                : "";
            } catch (e) {
              console.error("Token refresh error in resolve:", e);
            }
            if (!idToken || !authIsCurrent()) {
              finishRegistryAction();
              window.App?.showPopup?.("Your session has ended. Log in again to resolve this disagreement.");
              return;
            }

            const question = binding.question;
            const useOwnKeys = binding.useOwnKeys;
            const resolveUsageRunKey = useOwnKeys
              ? null
              : (globalThis.crypto?.randomUUID?.()
                || `${Date.now()}-${Math.random().toString(16).slice(2)}`);
            // Nur den Label-Text austauschen; der Pro-Chip bleibt dabei an
            // seinem Platz und der CSS-Spinner kann den Ladezustand anzeigen.
            const labelEl = button.querySelector(".diff-resolve-btn-label");
            const setLabel = function (text) {
              if (labelEl) labelEl.textContent = text;
              else button.textContent = text;
            };
            const originalLabel = labelEl ? labelEl.textContent : button.textContent;
            button.disabled = true;
            button.classList.add("is-loading");
            setLabel("Asking the models…");
            window.trackUmamiEvent?.("app_resolve_started", { positions: diff.positions.length });

            try {
              const response = await fetch("/resolve", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  id_token: idToken,
                  useOwnKeys: useOwnKeys,
                  usage_run_key: resolveUsageRunKey,
                  question: question,
                  claim: diff.claim,
                  positions: diff.positions,
                  bookmarkId: expectedBookmarkVersion ? binding.bookmarkId : null,
                  expectedBookmarkVersion: expectedBookmarkVersion || null,
                  openrouter_key: binding.credentials.openrouterKey || ""
                }),
                signal: actionController.signal
              });
              const data = await window.App.readJson(response).catch(() => ({}));
              if (!authIsCurrent()) return;
              if (!response.ok) {
                // Any form of the refusal ({detail}, {error: {…}}, flat; App.errorFields).
                const refusal = window.App.errorFields?.(data) || data?.detail || {};
                const refusalCode = refusal.error_code || refusal.code;
                if (refusalCode === "pro_required" || refusalCode === "plus_required") {
                  // Tier-Status war veraltet: Button in den Teaser-Zustand
                  // zurücksetzen und das Pro-Modal zeigen.
                  button.disabled = false;
                  button.classList.remove("is-loading");
                  setLabel(originalLabel);
                  showResolveProTeaser();
                  return;
                }
                throw window.App.httpError(response, data);
              }

              window.App.renderUsageDisplay(data, binding.auth);

              // Ergebnis am Widerspruch merken und Karte kennzeichnen; über
              // das Bookmark persistieren, damit es beim Wiederöffnen bleibt.
              // Prompt-Feld vor der Persistenz strippen: Bookmarks/Shares
              // bleiben schlank, die Prompt-Ansicht gibt es nur live.
              const persistedResolution = {
                outcome: data.outcome,
                results: (Array.isArray(data.results) ? data.results : []).map(function (r) {
                  return {
                    model: String(r?.model || ""),
                    decision: String(r?.decision || "error"),
                    position: String(r?.position || ""),
                    reason: String(r?.reason || "")
                  };
                })
              };
              diff.resolution = persistedResolution;
              if (boundContext) {
                boundContext.consensus.differencesData = binding.payload?.differencesData
                  || boundContext.consensus.differencesData;
                window.App.runRegistry?.update?.(boundContext.runId, function () {}, {
                  render: false,
                  eventType: "post-action"
                });
              }
              if (viewStillOwnsResult()) {
                renderResolveResult(resultBox, data);
                // Ladezustand beenden und Button entfernen (das [hidden]
                // greift erst durch die zugehoerige CSS-Regel).
                button.classList.remove("is-loading");
                button.hidden = true;
                markCardResolved(resultBox.closest(".diff-card"), data.outcome);
              }
              if (data.bookmark_persisted === true && binding.bookmarkId) {
                window.App.bookmarkUi?.invalidate?.(binding.bookmarkId);
                window.clearPreparedBookmarkShareResult?.();
                let resolvedBookmark = null;
                const persistedBookmark = boundContext?.persistence?.consensusBookmark;
                if (persistedBookmark) {
                  try {
                    resolvedBookmark = structuredClone(persistedBookmark);
                  } catch (_) {
                    try { resolvedBookmark = JSON.parse(JSON.stringify(persistedBookmark)); } catch (_) {}
                  }
                }
                if (!resolvedBookmark) resolvedBookmark = syntheticBookmark;
                const persistedDifferences = resolvedBookmark?.responses?.differences_data?.differences;
                const diffKey = JSON.stringify([
                  String(diff.claim || "").trim(),
                  Array.isArray(diff.positions) ? diff.positions : []
                ]);
                if (Array.isArray(persistedDifferences)) {
                  const persistedDiff = persistedDifferences.find(function (item) {
                    return JSON.stringify([
                      String(item?.claim || "").trim(),
                      Array.isArray(item?.positions) ? item.positions : []
                    ]) === diffKey;
                  });
                  if (persistedDiff) persistedDiff.resolution = persistedResolution;
                }
                resolvedBookmark.share_result_id = "";
                const resolvedVersionParts = window.App.bookmarkUi?.versionParts?.(resolvedBookmark) || [];
                if (boundContext) {
                  boundContext.consensus.resultId = null;
                  if (boundContext.consensus.bookmarkPayload) {
                    boundContext.consensus.bookmarkPayload.resultId = null;
                  }
                  boundContext.persistence.consensusBookmark = resolvedBookmark;
                  boundContext.persistence.consensusVersionParts = resolvedVersionParts.slice();
                  const exactDifferences = resolvedBookmark?.responses?.differences_data;
                  if (exactDifferences) {
                    boundContext.consensus.differencesData = exactDifferences;
                    if (boundContext.consensus.bookmarkPayload) {
                      boundContext.consensus.bookmarkPayload.differencesData = exactDifferences;
                    }
                  }
                }
                window.currentBookmarkShareResultContext = {
                  bookmarkId: binding.bookmarkId,
                  versionParts: resolvedVersionParts
                };
              }
              window.trackUmamiEvent?.("app_resolve_completed", {
                outcome: data.outcome,
                bookmark_persisted: data.bookmark_persisted === true
              });
            } catch (error) {
              if (error?.name === "AbortError" || !authIsCurrent()) return;
              console.error("Resolve round failed:", error);
              resultBox.innerHTML = "";
              const note = document.createElement("div");
              note.className = "resolve-outcome is-error";
              note.textContent = window.App.userError(error, { fallback: "The resolve round failed. Try again." });
              resultBox.appendChild(note);
              resultBox.hidden = false;
              button.disabled = false;
              button.classList.remove("is-loading");
              setLabel(originalLabel);
              window.trackUmamiEvent?.("app_resolve_completed", { outcome: "request_error" });
            } finally {
              finishRegistryAction();
            }
          }

          const RESOLVE_BTN_ICON =
            '<svg class="diff-resolve-icon" viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" fill="none" '
            + 'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            + '<path d="M2 5h9M11 5 8.8 2.8M11 5 8.8 7.2"/>'
            + '<path d="M14 11H5M5 11l2.2-2.2M5 11l2.2 2.2"/></svg>';

          function buildResolveSection(diff) {
            if (diff.type !== "contradiction") return null;

            const wrap = document.createElement("div");
            wrap.className = "diff-resolve";
            const resultBox = document.createElement("div");
            resultBox.className = "diff-resolve-result";
            resultBox.hidden = true;

            // Bereits gelöster Widerspruch (persistiert im Bookmark): Ergebnis
            // direkt zeigen, kein Button. Die Karten-Kennzeichnung übernimmt
            // renderDifferenceCards nach dem Einhängen der Karte.
            if (diff.resolution && RESOLVE_STATUS[diff.resolution.outcome]) {
              renderResolveResult(resultBox, diff.resolution);
              wrap.appendChild(resultBox);
              return wrap;
            }

            const involved = new Set();
            diff.positions.forEach(function (pos) {
              (pos.models || []).forEach(function (m) { if (MODEL_BOX_IDS[m]) involved.add(m); });
            });
            if (involved.size < 2 || diff.positions.length < 2) return null;

            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "diff-resolve-btn";
            btn.insertAdjacentHTML("afterbegin", RESOLVE_BTN_ICON);
            const label = document.createElement("span");
            label.className = "diff-resolve-btn-label";
            label.textContent = "Resolve with the models";
            btn.appendChild(label);
            btn.title = "Ask the disagreeing models to re-examine this point against each other’s position (uses 1 request)";
            // Pro-Chip immer zeigen: Free-Nutzer sehen den Hinweis (Klick öffnet
            // die Kosten-Erklaerung), Pro-Nutzer die gleiche klare Kennzeichnung.
            const chip = document.createElement("span");
            chip.className = "pro-badge diff-resolve-pro-chip";
            // Resolve laeuft auf dem Standard-Judge und ist deshalb ab Plus
            // frei; das Chip nennt die niedrigste Stufe, die es freischaltet.
            chip.textContent = "Plus";
            btn.appendChild(chip);
            if (!window.isUserPlus) {
              btn.classList.add("is-pro-locked");
              btn.title = "Off by default: a Resolve round is a second full round of model calls";
            }

            btn.addEventListener("click", function () {
              if (!window.isUserPlus) {
                showResolveProTeaser();
                return;
              }
              runResolveRound(diff, btn, resultBox);
            });
            wrap.append(btn, resultBox);
            return wrap;
          }

          // --- Differences-Panel ----------------------------------------------
          // Die Unterschiede sind nicht mehr die zweite Spalte neben der
          // Antwort, sondern ein zugeklappter Ueberblick darunter. Waehrend der
          // Synthese ist er offen (Spinner), danach entscheidet das Ergebnis.
          const DIFF_SUMMARY_RUNNING = "Differences";
          const DIFF_SUMMARY_DONE = "See all differences";

          function differencesPanel() {
            return $("consensusDifferencesPanel");
          }

          function setPanelState(open, label) {
            const panel = differencesPanel();
            if (!panel) return;
            panel.open = !!open;
            const labelEl = panel.querySelector(".consensus-differences-summary-label");
            if (labelEl && label) labelEl.textContent = label;
          }

          window.App.differencesPanel = {
            // Zu, nicht offen: der Spinner in diesem Panel ist entfallen, weil
            // der gefuehrte Lauf dieselbe Phase schon ansagt. Ein aufgeklapptes
            // leeres Panel waere die dritte Anzeige desselben Vorgangs.
            setSynthesizing: function () { setPanelState(false, DIFF_SUMMARY_RUNNING); },
            // Freitext-Fallback: der alte Block muss sichtbar und aufgeklappt
            // erscheinen, sonst verschwindet die Analyse stillschweigend.
            expandForFallback: function () { setPanelState(true, DIFF_SUMMARY_DONE); }
          };

          // --- Differences-Karten --------------------------------------------
          // Baut die Karten in einen beliebigen Container, damit der Live-Fuss
          // und ein archivierter Turn dieselbe Darstellung teilen. Ein
          // archivierter Turn bekommt die statische Fassung: seine Sprunglinks
          // zeigten sonst auf die Antwortboxen des NEUESTEN Laufs, und eine
          // Resolve-Runde gehoert immer zum aktiven Lauf.
          function differenceRank(diff) {
            if (diff.type !== "contradiction") return 2;
            return diff.severity === "minor" ? 1 : 0;
          }

          // Die Schwere in Worten, fuer Screenreader; ohne Severity (alte
          // Bookmarks/Snapshots) das neutrale "Contradiction".
          function differenceMeaning(diff) {
            if (diff.type !== "contradiction") return "Different emphasis, not a contradiction";
            if (diff.severity === "major") return "Critical contradiction";
            if (diff.severity === "minor") return "Minor contradiction about a detail";
            return "Contradiction";
          }

          // Karte zum Datenindex der Differences-Liste. Die Karten stehen nach
          // Schwere sortiert; die Kartenposition ist deshalb kein Index mehr.
          function differenceCardAt(container, index) {
            if (!container) return null;
            const id = String(index).replace(/[^\w-]/g, "");
            return container.querySelector('.diff-card[data-difference-index="' + id + '"]')
              || (typeof index === "number" ? container.querySelectorAll(".diff-card")[index] : null) || null;
          }
          window.App.differenceCardAt = differenceCardAt;

          // Eine Karte unter den gebuendelten kleineren Unterschieden braucht
          // auch ihre Gruppe offen, sonst bleibt sie unsichtbar.
          function openDifferenceCard(card) {
            card.open = true;
            const group = card.closest("details.diff-more");
            if (group) group.open = true;
          }

          // Differenzen von vor 2026-10-16 erzaehlen beide Seiten mit den
          // Anonym-Labels des Judges ("Model F sagt, ...", "Die Synthese sagt,
          // dass ..."), und die Ueberschrift erzaehlt dasselbe noch einmal. In
          // der Gegenueberstellung steht jede Behauptung nur einmal: die
          // Zuschreibung faellt weg (wer es sagt, steht darunter), "die
          // Synthese" ist die Antwort selbst und damit deren Seite, und ein
          // "Model X" mit genau einem Modell bekommt dessen echten Namen.
          const LEGACY_ATTRIBUTION = new RegExp(
            "^\\s*(?:(?:Models?|Modell)\\s+([A-Z])|(?:die|the)\\s+(?:Synthese|synthesis|Konsensantwort|consensus(?:\\s+answer)?))"
            + "\\s+(?:sagt|says|meldet|reports|beschreibt|describes|behauptet|claims|states|nennt|names|schreibt|writes|"
            + "argumentiert|argues|erklärt|explains|betont|stresses)\\s*,?\\s*(?:dass\\s+|that\\s+)?", "i");
          const LEGACY_NARRATIVE = /\b(?:Models?|Modelle?)\s+[A-Z]\b|\b(?:Synthese|synthesis|Konsensantwort|Konsens|consensus answer)\b/;
          // Steht "Model X" am Anfang einer Position mit genau einem Modell,
          // ist X dieses Modell. Alle Differenzen eines Prueflaufs teilen
          // dieselben Labels, die Zuordnung gilt also fuer die ganze Liste.
          const LEGACY_LABEL = /\b(?:Model|Modell)\s+([A-Z])\b/g;

          const SYNTHESIS_SUBJECT = /^\s*die\s+(?:Synthese|Konsensantwort)/i;

          function legacyModelNames(differences, labelFor) {
            const names = {};
            differences.forEach(function (diff) {
              (diff.positions || []).forEach(function (pos) {
                const match = /^\s*(?:Model|Modell)\s+([A-Z])\b/.exec(pos.stance || "");
                if (match && pos.models.length === 1) names[match[1]] = labelFor(pos.models[0]);
              });
            });
            return names;
          }

          function withModelNames(text, names) {
            return String(text || "").replace(LEGACY_LABEL, function (label, letter) {
              return names[letter] || label;
            });
          }

          // Eine Behauptung ist eine Seite (Live-Befund 2026-10-21): der Judge
          // nannte den Satz der Antwort einmal fuer Luna und einmal fuer zwei
          // weitere Modelle, und die Karte zeigte ihn zweimal mit "vs"
          // dazwischen. Dieselbe Regel wie _normalize_differences im Backend,
          // damit auch gespeicherte Chats jede Behauptung nur einmal zeigen:
          // gleiche Aussage = eine Seite, jedes Modell nur auf seiner ersten.
          function claimKey(text) {
            return String(text || "").replace(/\s+/g, " ").trim().toLowerCase()
              .replace(/[\s.!?;:,…。！？]+$/u, "");
          }

          function mergedPositions(positions) {
            const merged = [];
            const taken = new Set();
            positions.forEach(function (pos) {
              const models = [];
              (pos.models || []).forEach(function (model) {
                if (!taken.has(model)) models.push(model);
              });
              const key = claimKey(pos.stance || pos.quote);
              const same = key && merged.find(function (side) {
                return claimKey(side.stance || side.quote) === key;
              });
              models.forEach(function (model) { taken.add(model); });
              if (same) {
                same.models = same.models.concat(models);
                if (!same.quote && pos.quote) same.quote = pos.quote;
                if (pos.in_answer === true) same.in_answer = true;
                return;
              }
              if (models.length) merged.push(Object.assign({}, pos, { models: models }));
            });
            return merged;
          }

          function readableDifference(diff, labelFor, names) {
            names = names || legacyModelNames([diff], labelFor);
            const hasAnswer = diff.positions.some(function (pos) { return pos.in_answer === true; });
            let legacyAnswer = false;
            const positions = diff.positions.map(function (pos) {
              const match = LEGACY_ATTRIBUTION.exec(pos.stance || "");
              // Nach "dass" steht das Verb am Ende: ohne den Hauptsatz waere
              // der Rest kein Satz. Dann bleibt der Satz, nur der Sprecher
              // bekommt seinen Namen ("Die Antwort", das echte Modell).
              if (match && /dass\s+$/i.test(match[0])) {
                const speaker = withModelNames(pos.stance, names).replace(SYNTHESIS_SUBJECT, "Die Antwort");
                const kept = Object.assign({}, pos, { stance: speaker });
                if (!match[1] && !hasAnswer && !legacyAnswer) {
                  kept.in_answer = true;
                  legacyAnswer = true;
                }
                return kept;
              }
              const rest = match ? pos.stance.slice(match[0].length).trim() : "";
              if (!rest) {
                const named = withModelNames(pos.stance, names);
                return pos.stance && named !== pos.stance ? Object.assign({}, pos, { stance: named }) : pos;
              }
              const readable = Object.assign({}, pos, {
                stance: withModelNames(rest.charAt(0).toUpperCase() + rest.slice(1), names)
              });
              if (!match[1] && !hasAnswer && !legacyAnswer) {
                readable.in_answer = true;
                legacyAnswer = true;
              }
              return readable;
            });
            // Eine kurze Themenzeile ("Tesla Model S") ist keine Erzaehlung.
            const narrative = String(diff.claim || "").length > 60 && LEGACY_NARRATIVE.test(diff.claim);
            return { claim: withModelNames(diff.claim, names), narrative: narrative, positions: mergedPositions(positions) };
          }

          // Gelbe Saetze der Satzpruefung mit benannter Streitstelle (Max
          // 2026-10-23: was im Text markiert ist, steht auch in der Liste):
          // als kleinere Unterschiede, Kopf ihr Satz mit seiner Stelle, dann
          // die Gegenseiten. Ein Satz, den schon ein Unterschied traegt,
          // bleibt dessen Karte. `claims` wie die Marken sie filtern; ihr
          // Index dort ist die Kennung "c<i>" der Karte (data-difference-index).
          function usableClaims(claims) {
            return (Array.isArray(claims) ? claims : [])
              .filter(function (c) { return c && c.anchor && Array.isArray(c.agree) && Array.isArray(c.dissent); });
          }

          function claimTargets(claim) {
            return claim.dissent
              .map(function (item) { return item && typeof item.target === "string" ? item.target.trim() : ""; })
              .filter(Boolean);
          }

          function sentenceKey(text) {
            return claimKey(visibleWords(text));
          }

          function listedClaim(claim, differences) {
            if (claimCoverage(claim) !== "split" || !claimTargets(claim).length) return false;
            const key = sentenceKey(claim.anchor);
            return !(differences || []).some(function (diff) { return sentenceKey(diff.consensus_anchor) === key; });
          }

          function claimDifference(claim) {
            return {
              claim: "Not every model agrees",
              consensus_anchor: claim.anchor,
              type: "contradiction",
              severity: "minor",
              positions: [{ models: claim.agree.map(cardModel), stance: "", quote: "", in_answer: true }]
                .concat(dissentSides(claim).map(function (side) {
                  return { models: side.models.map(cardModel), stance: side.quote, quote: "" };
                }))
            };
          }

          function buildDifferenceCards(cards, differences, modelCount, options) {
            const opts = options || {};
            const isStatic = !!opts.static;
            const labelFor = typeof opts.modelLabel === "function"
              ? opts.modelLabel
              : modelDisplayName;
            cards.innerHTML = "";
            const claimEntries = [];
            usableClaims(opts.claims).forEach(function (claim, index) {
              if (!listedClaim(claim, differences)) return;
              claimEntries.push({ diff: claimDifference(claim), claim: claim, index: "c" + index,
                order: differences.length + index });
            });

            if (!differences.length && !claimEntries.length) {
              // Flacher Empty-State: grüner Punkt + zwei Textzeilen statt Box.
              const empty = document.createElement("div");
              empty.className = "diff-empty-state";
              const dot = document.createElement("span");
              dot.className = "sev-dot is-ok";
              dot.setAttribute("aria-hidden", "true");
              const textWrap = document.createElement("div");
              textWrap.className = "diff-empty-text";
              const headline = document.createElement("div");
              headline.className = "diff-empty-headline";
              headline.textContent = "No substantive contradictions found across the "
                + modelCount + " answers.";
              const note = document.createElement("div");
              note.className = "diff-empty-note";
              note.textContent = "Agreement is a good signal, but not a guarantee of correctness.";
              textWrap.append(headline, note);
              empty.append(dot, textWrap);
              cards.appendChild(empty);
            } else {
              // Kritische Widersprueche zuerst, dann Details, dann andere
              // Gewichtungen; innerhalb einer Stufe bleibt die Judge-Reihenfolge.
              // Inline-Marker verlinken weiter per Datenindex
              // (data-difference-index), nicht per Kartenposition.
              const sorted = differences
                .map(function (diff, index) { return { diff: diff, index: index, order: index }; })
                .concat(claimEntries)
                .sort(function (a, b) {
                  return differenceRank(a.diff) - differenceRank(b.diff) || a.order - b.order;
                });
              const names = legacyModelNames(differences, labelFor);
              // Gibt es kritische Widersprueche, stehen die kleineren (ab zwei)
              // gebuendelt dahinter: sonst wird aus wenigen wichtigen Punkten
              // eine lange, gleichfoermige Liste.
              const smaller = sorted.filter(function (entry) { return differenceRank(entry.diff) > 0; });
              let smallerBody = null;
              if (smaller.length >= 2 && smaller.length < sorted.length) {
                const group = document.createElement("details");
                group.className = "diff-more";
                const groupSummary = document.createElement("summary");
                groupSummary.className = "diff-more-summary";
                groupSummary.textContent = smaller.length + " smaller differences";
                smallerBody = document.createElement("div");
                smallerBody.className = "diff-more-body";
                group.append(groupSummary, smallerBody);
              }
              sorted.forEach(function (entry) {
                const diff = entry.diff;
                const readable = readableDifference(diff, labelFor, names);
                const isVersus = diff.type === "contradiction" && readable.positions.length > 1;
                const card = document.createElement("details");
                card.dataset.differenceIndex = String(entry.index);
                let cardClass = "diff-card " + (diff.type === "contradiction" ? "is-contradiction" : "is-emphasis");
                if (diff.type === "contradiction" && diff.severity === "major") cardClass += " is-major";
                if (entry.claim) cardClass += " is-split";
                card.className = cardClass;
                // Jede Karte wartet zugeklappt auf ihren Kopf, die kleineren
                // dazu in ihrer Gruppe: wer sich dafuer interessiert, oeffnet
                // sie einzeln (Max 2026-10-23).
                card.open = false;

                // Ein Widerspruch sind Behauptungen, die sich gegenueberstehen:
                // jede Seite ist ein Satz, immer untereinander, damit zwei und
                // drei Seiten gleich aussehen. Die Seite, die die Antwort
                // vertritt, steht vorn.
                const ordered = readable.positions.slice().sort(function (a, b) {
                  return (b.in_answer === true) - (a.in_answer === true);
                });
                // Seit 2026-10-23 in der Reihenfolge, in der man es versteht
                // (Max: "zuerst WAS die Ausgangssituation ist, DANN die
                // Aussage, die konkurriert, DANN welches Modell was sagt"):
                // Im Leser fehlt die Antwort, also ist ihr markierter Satz
                // woertlich der Kopf der Karte ("In the answer", in der Farbe
                // seiner Marke, die auch die Schwere zeigt; das Thema leise
                // darueber, kein Punkt), dann die Gegenseite ("In contrast"
                // statt "vs"), darunter je wer sie vertritt. Ohne Satz in der
                // Antwort bleibt das Thema der Kopf, ein kritisches mit rotem
                // Punkt. Die Etikettzeile ("● Critical") ist weg; Screenreader
                // hoeren die Schwere vorab (diff-card-meaning).
                const answerAnchor = String(diff.consensus_anchor || "").replace(/\[S?\d+(?:\s*,\s*S?\d+)*\]/gi, "").trim();
                const hasAnswerSide = ordered.some(function (pos) { return pos.in_answer === true; });
                const opensOnAnswer = hasAnswerSide && !!answerAnchor;

                const summary = document.createElement("summary");
                summary.className = "diff-card-summary";
                const meaning = document.createElement("span");
                meaning.className = "visually-hidden diff-card-meaning";
                meaning.append(differenceMeaning(diff), document.createElement("span"));
                meaning.lastChild.textContent = ": ";
                const claimEl = document.createElement("span");
                if (opensOnAnswer) {
                  // Das Thema leise darueber, auch zugeklappt: viele Saetze
                  // sagen allein nichts ("Das ist unbestaetigt.", "Er ist CEO
                  // ..."; Max' echte Daten 2026-10-23), das Thema gibt ihnen
                  // ihren Zusammenhang. Dass der Satz aus der Antwort stammt,
                  // sagt seine Marke.
                  const lead = document.createElement("span");
                  lead.className = "diff-card-topic";
                  if (!entry.claim) lead.setAttribute("data-i18n-skip", "");
                  lead.textContent = readable.claim;
                  claimEl.className = "diff-card-claim is-answer-text";
                  const answerMark = document.createElement("span");
                  answerMark.className = "diff-answer-mark";
                  renderInlineMarkdown(answerMark, answerAnchor);
                  // Ein Satz der Satzpruefung: farbig nur seine Stelle, wie im Text.
                  if (entry.claim) wrapSpots([answerMark], claimTargets(entry.claim));
                  claimEl.appendChild(answerMark);
                  summary.append(meaning, lead, claimEl);
                } else {
                  // Erzaehlt die Ueberschrift beide Seiten (alte Daten), steht
                  // sie nur im zugeklappten Zustand: offen sagen es die Seiten.
                  claimEl.className = "diff-card-claim" + (readable.narrative && isVersus ? " is-narrative" : "");
                  if (diff.type === "contradiction" && diff.severity === "major") {
                    const sevDot = document.createElement("span");
                    sevDot.className = "sev-dot is-crit";
                    sevDot.setAttribute("aria-hidden", "true");
                    claimEl.appendChild(sevDot);
                  }
                  claimEl.append(readable.claim);
                  summary.append(meaning, claimEl);
                }
                card.appendChild(summary);

                const body = document.createElement("div");
                body.className = "diff-card-body";
                const sides = document.createElement("div");
                sides.className = "diff-sides" + (isVersus ? " is-versus" : "");
                ordered.forEach(function (pos, sideIndex) {
                  const posEl = document.createElement("div");
                  posEl.className = "diff-position" + (pos.in_answer === true ? " is-answer" : "");
                  // Die Seite der Antwort unter einem Kopf, der ihren Satz schon
                  // zeigt: nur noch, wer sie vertritt.
                  const shownAbove = opensOnAnswer && pos.in_answer === true;
                  const lead = shownAbove ? ""
                    : pos.in_answer === true ? "In the answer"
                    : (hasAnswerSide || sideIndex > 0) ? (diff.type === "contradiction" ? "In contrast" : "Weighted differently")
                    : "";
                  if (lead) {
                    const leadEl = document.createElement("div");
                    leadEl.className = "diff-position-lead";
                    leadEl.textContent = lead;
                    posEl.appendChild(leadEl);
                  }
                  if (!shownAbove && (pos.stance || pos.quote)) {
                    const stance = document.createElement("div");
                    stance.className = "diff-position-stance";
                    renderInlineMarkdown(stance, pos.stance || pos.quote);
                    posEl.appendChild(stance);
                  }
                  // Unter der Behauptung eine leise Zeile (2026-10-21): wer das
                  // sagt, ob die Antwort diese Seite vertritt, und das Zitat
                  // auf Wunsch. Vorher stand jedes davon in eigener Zeile.
                  const meta = document.createElement("div");
                  meta.className = "diff-position-meta";

                  // Wer das sagt: Icon + Name; bei mehreren Modellen nur die
                  // Icons und die Anzahl (die Namen bleiben Linktext und
                  // Tooltip). Ist die Originalantwort erreichbar, ist genau
                  // dieses Paar der Sprunglink. Gleiche Modell-Icons und
                  // Theme-Behandlung wie im Antwort-Leser.
                  const label = document.createElement("div");
                  label.className = "diff-position-label" + (pos.models.length > 1 ? " is-group" : "");
                  const canJump = function (model) {
                    if (isStatic && !opts.answerNavigation) return false;
                    return opts.answerNavigation ? opts.answerNavigation.canOpen(model) : !!MODEL_BOX_IDS[model];
                  };
                  pos.models.forEach(function (model) {
                    const name = labelFor(model);
                    const jumps = canJump(model);
                    const entry = document.createElement(jumps ? "button" : "span");
                    entry.className = "diff-position-model" + (jumps ? " diff-jump-link" : "");
                    const mark = document.createElement("span");
                    mark.className = "diff-position-icon";
                    mark.setAttribute("aria-hidden", "true");
                    const original = $(MODEL_BOX_IDS[model] || "")?.querySelector("img");
                    if (original) {
                      const icon = document.createElement("img");
                      icon.src = original.src;
                      icon.alt = "";
                      ["chatgpt-logo", "grok-logo", "mono-logo"].forEach(function (cls) {
                        if (original.classList.contains(cls)) icon.classList.add(cls);
                      });
                      mark.appendChild(icon);
                    } else {
                      mark.textContent = name.slice(0, 1).toUpperCase();
                    }
                    const nameEl = document.createElement("span");
                    nameEl.className = "diff-position-name";
                    nameEl.textContent = name;
                    entry.append(mark, nameEl);
                    entry.title = name;
                    if (jumps) {
                      entry.type = "button";
                      entry.title = "Open the full answer from " + name;
                      entry.setAttribute("aria-label", "Open the full answer from " + name);
                      entry.addEventListener("click", function () {
                        if (opts.answerNavigation) opts.answerNavigation.open(model, pos.quote, entry);
                        else jumpToModelAnswer(model, pos.quote);
                      });
                    }
                    label.appendChild(entry);
                  });
                  if (pos.models.length > 1) {
                    const count = document.createElement("span");
                    count.className = "diff-position-count";
                    count.setAttribute("aria-hidden", "true");
                    count.textContent = pos.models.length + " models";
                    label.appendChild(count);
                  }
                  if (pos.models.length) meta.appendChild(label);
                  if (meta.firstChild || (pos.stance && pos.quote)) posEl.appendChild(meta);

                  // Das Zitat belegt die Behauptung, es wiederholt sie: erst
                  // auf Wunsch (Klick-Delegation unten, auch fuer Kopien).
                  if (pos.stance && pos.quote) {
                    const toggle = document.createElement("button");
                    toggle.type = "button";
                    toggle.className = "diff-quote-toggle";
                    toggle.setAttribute("aria-expanded", "false");
                    toggle.textContent = "Show quote";
                    const quote = document.createElement("blockquote");
                    quote.className = "diff-position-quote";
                    quote.hidden = true;
                    renderInlineMarkdown(quote, pos.quote);
                    meta.appendChild(toggle);
                    posEl.appendChild(quote);
                  }
                  sides.appendChild(posEl);
                });
                body.appendChild(sides);

                // Im Archiv nur das PERSISTIERTE Ergebnis, nie der Auslöser:
                // eine Resolve-Runde laeuft gegen die Modelle des aktiven Laufs.
                // Deshalb faellt jeder Knopf raus, auch bei einer Resolution
                // mit unbekanntem Ausgang — die baut sonst wieder den Starter.
                const resolveSection = (entry.claim || (isStatic && !diff.resolution))
                  ? null
                  : buildResolveSection(diff);
                if (resolveSection && isStatic) {
                  resolveSection.querySelectorAll("button").forEach(b => b.remove());
                }
                if (resolveSection && resolveSection.childNodes.length) {
                  body.appendChild(resolveSection);
                }
                card.appendChild(body);
                (smallerBody && differenceRank(diff) > 0 ? smallerBody : cards).appendChild(card);
                // Persistierte Resolve-Runde (z. B. aus einem Bookmark): Karte
                // direkt als gelöst/bestätigt kennzeichnen.
                if (diff.resolution) markCardResolved(card, diff.resolution.outcome);
              });
              // Die Gruppe steht hinter den kritischen Karten.
              if (smallerBody) cards.appendChild(smallerBody.parentNode);
            }
            return cards;
          }

          function renderDifferenceCards(differences, modelCount, claims) {
            const cards = $("differencesCards");
            const diffP = document.querySelector("#consensusResponse .consensus-differences p");
            if (!cards) return;
            buildDifferenceCards(cards, differences, modelCount, { claims: claims });

            cards.hidden = false;
            if (diffP) {
              diffP.innerHTML = "";
              diffP.hidden = true;
            }
            // Strukturierte Karten liegen ab hier zugeklappt unter der Antwort.
            setPanelState(false, DIFF_SUMMARY_DONE);
          }

          // Ein archivierter Turn hat dieselben strukturierten Daten wie der
          // Live-Lauf — bis 2026-08-17 fiel er trotzdem auf den Freitext des
          // Judges zurueck und zeigte dabei sogar dessen "BestModel:"-Zeile.
          // Gleiche Daten, gleiche Karten; interaktiv ist nur der aktive Lauf.
          function renderStoredDifferenceCards(container, differencesData, options) {
            if (!container || !differencesData || typeof differencesData !== "object") {
              return false;
            }
            if (!Array.isArray(differencesData.differences)) return false;
            const differences = differencesData.differences.filter(
              d => d && d.claim && Array.isArray(d.positions) && d.positions.length
            );
            const modelCount = (Array.isArray(differencesData.models_compared)
              && differencesData.models_compared.length)
              || Number(differencesData.agreement?.model_count)
              || 0;
            buildDifferenceCards(container, differences, modelCount, {
              static: true,
              claims: differencesData.claims,
              modelLabel: options && options.modelLabel,
              answerNavigation: options && options.answerNavigation
            });
            return true;
          }

          // --- Reset & Haupteinstieg -----------------------------------------
          function resetConsensusInsights() {
            closeClaimPopover();
            hideHoverPreview();
            const verdict = $("consensusVerdict");
            if (verdict) {
              verdict.hidden = true;
              verdict.innerHTML = "";
              verdict.classList.remove("is-calm", "is-warn");
            }
            const cards = $("differencesCards");
            if (cards) {
              cards.hidden = true;
              cards.innerHTML = "";
            }
            const fallbackBox = $("consensusClaimsFallback");
            if (fallbackBox) {
              fallbackBox.hidden = true;
              fallbackBox.innerHTML = "";
            }
            // Nur der aktive Consensus wird fuer den naechsten Lauf
            // zurueckgesetzt. Statische Follow-up-Turns in #threadHistory
            // behalten ihre sichtbaren Quoten und Marken.
            const insightRoot = window.App.consensusBodyEl?.() || document;
            insightRoot.querySelectorAll(".claim-badge").forEach(function (el) { el.remove(); });
            // Inline-Markierungen auflösen: Span entfernen, Text an Ort und
            // Stelle lassen. normalize() führt die Textknoten wieder zusammen,
            // damit eine erneute Ankersuche nicht an Fragmenten scheitert.
            // Die Stellen-Spans (.cx-spot) in den Satz-Spans gehen mit: die
            // Reihenfolge ist egal, jeder Span gibt nur seine Kinder ab.
            insightRoot.querySelectorAll(".cx-claim:not(.pc-claim) .cx-spot, .cx-claim:not(.pc-claim)").forEach(function (span) {
              const parent = span.parentNode;
              if (!parent) return;
              while (span.firstChild) parent.insertBefore(span.firstChild, span);
              span.remove();
              parent.normalize();
            });
            const diffP = document.querySelector("#consensusResponse .consensus-differences p");
            if (diffP) diffP.hidden = false;
          }

          function renderConsensusInsights(data, includedCount, options = {}) {
            resetConsensusInsights();
            if (!data || typeof data !== "object") return false;

            const claims = (Array.isArray(data.claims) ? data.claims : [])
              .filter(c => c && c.anchor && Array.isArray(c.agree) && Array.isArray(c.dissent));
            const differences = (Array.isArray(data.differences) ? data.differences : [])
              .filter(d => d && d.claim && Array.isArray(d.positions) && d.positions.length);
            const modelCount = (Array.isArray(data.models_compared) && data.models_compared.length)
              || includedCount || 0;
            const modelsCompared = Array.isArray(data.models_compared)
              ? data.models_compared : [];
            const agreement = (data.agreement && typeof data.agreement === "object") ? data.agreement : null;
            const judge = (data.judges && typeof data.judges === "object"
              && data.judges.differences && typeof data.judges.differences === "object")
              ? data.judges.differences : null;

            renderVerdictHeader(differences, modelCount, agreement, judge);
            // Karten zuerst: die Inline-Marker verlinken per Index auf sie.
            renderDifferenceCards(differences, modelCount, claims);
            const marks = renderInlineMarkers(claims, differences, modelsCompared, {
              sources: Array.isArray(options.sources) ? options.sources : undefined
            }) || {};
            window.trackUmamiEvent?.("app_consensus_insights_rendered", {
              claims: claims.length,
              // Wie viele Claims wirklich IM Text markiert wurden statt nur in
              // der Fallback-Liste zu landen: die eine Zahl, an der sich eine
              // Aenderung an Ankern oder Ankersuche messen laesst.
              claims_anchored: marks.claims_anchored ?? null,
              claims_unanchored: marks.claims_unanchored ?? null,
              diffs_unanchored: marks.diffs_unanchored ?? null,
              // Wie sich die Abdeckung auf die drei Claim-Zustaende verteilt:
              // ein steigender thin-Anteil heisst, dass die Modelle an der
              // Konsensantwort vorbeireden - nicht, dass sie streiten.
              claims_supported: marks.claims_supported ?? null,
              claims_split: marks.claims_split ?? null,
              claims_thin: marks.claims_thin ?? null,
              differences: differences.length,
              contradictions: differences.filter(d => d.type === "contradiction").length,
              major_contradictions: differences.filter(d => d.type === "contradiction" && d.severity === "major").length,
              agreement_score: agreement ? agreement.score : null
            });
            return true;
          }

          // Erst nach Aufbau des gesamten Moduls anwenden: Im versteckten
          // Startzustand schliesst applyConsensusMarkerVisibility ein eventuell
          // offenes Popover und braucht deshalb dessen inzwischen initialisierten
          // Modal-State.
          readMarkerPreferences();
          restoreClaimCounts();
          highlightSelect?.addEventListener("change", function () {
            const show = this.value !== "none";
            if (show) highlightMode = Object.prototype.hasOwnProperty.call(MARKER_FILTERS, this.value) ? this.value : DEFAULT_HIGHLIGHT_MODE;
            settings.set("consensus_highlights", show ? highlightMode : "none");
            applyConsensusMarkerVisibility(show, true);
          });
          window.addEventListener("pageshow", restoreConsensusMarkerVisibility);
          // The account's choice arrived (server, another tab, sign-out).
          settings.onChange("consensus_highlights", function (detail) {
            if (detail.source !== "local") restoreConsensusMarkerVisibility();
          });
          settings.onChange("claim_counts", function (detail) {
            if (detail.source !== "local") restoreClaimCounts();
          });

          // Zitat einer Differenz-Seite ein-/ausklappen: delegiert, weil der
          // Antwort-Leser die Karten verschiebt und Kopien davon zeigt.
          document.addEventListener("click", function (event) {
            const toggle = event.target.closest?.(".diff-quote-toggle");
            const quote = toggle?.closest(".diff-position")?.querySelector(".diff-position-quote");
            if (!quote) return;
            quote.hidden = !quote.hidden;
            toggle.setAttribute("aria-expanded", String(!quote.hidden));
            toggle.textContent = quote.hidden ? "Show quote" : "Hide quote";
          });

          window.renderConsensusInsights = renderConsensusInsights;
          window.renderStoredConsensusClaims = renderStoredConsensusClaims;
          window.renderStoredDifferenceCards = renderStoredDifferenceCards;
          window.resetConsensusInsights = resetConsensusInsights;
          window.jumpToModelAnswer = jumpToModelAnswer;
          // The same card for a checked sentence of the user's own message
          // (passage-check.js), so both read and close alike, and the same
          // hover preview before it (attachPreview). hidePreview: marks taken
          // off outside this module (agent-review.js) take their preview along.
          window.App = window.App || {};
          window.App.claimPopover = { open: openClaimPopover, close: closeClaimPopover,
            attachPreview: attachClaimPreview, hidePreview: hidePreviewWithin };
        })();

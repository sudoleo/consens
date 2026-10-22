// =====================================================================
// settings-search.js
// The search field above the Settings sections. It looks through every
// section at once and shows only the settings that match, under their
// section's title; clearing it or picking a section brings the tabs back.
//
// What finds a setting: the words it shows (title, description, choices, in
// the page's language), the English and German words of its
// data-settings-keywords and those of its section. Every word of the query
// has to be found, as
//   * the start of a word ("anim" -> "Animations"), from four letters also
//     any part of one ("prompt" -> "Systemprompt"),
//   * a word that runs on over a hyphen or a space ("buchstabenanimation"),
//   * or with a typo: a letter wrong, missing, extra or two swapped, one from
//     five letters on, two from nine.
// Umlauts match spelled out and plain (ä = ae = a, ß = ss); filler words
// ("the", "die", "off", "aus") need not be found. Settings found without a
// typo win: a typo match shows only when nothing matches exactly.
// Matched words in view are tinted with the CSS Custom Highlight API: no node
// is added, so the i18n observer and the controls see nothing change.
//
// Panels follow App.settingsTabs; an unavailable tab's panel (Agent for an
// account without it, Account for a guest) is never searched.
// Exports: window.App.settingsSearch { matches, run, clear, active }
// =====================================================================
(() => {
  const App = window.App = window.App || {};

  const EXACT = 2;
  const TYPO = 1;
  // Words a query may carry that name no setting.
  const FILLERS = new Set([
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "off", "for", "with", "my", "how", "do", "i", "can",
    "setting", "settings", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "und", "oder", "von",
    "zu", "im", "am", "aus", "mit", "fuer", "fur", "mein", "meine", "ich", "wie", "kann", "man", "ist", "bei",
    "auf", "einstellung", "einstellungen",
  ]);
  // Text that is not the setting's own words: saved memories, status lines.
  const NOT_SETTING_TEXT = "ul, [role='status'], [aria-live], textarea, script, style, svg"; // i18n-ignore
  const HIGHLIGHT = "settings-search";

  // Lower case without accents; ä, ö, ü and ß spelled out (`plain`: as their
  // base letter instead).
  function fold(text, plain) {
    let folded = String(text).toLowerCase();
    folded = plain
      ? folded.replace(/ß/g, "ss")
      : folded.replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss");
    return folded.normalize("NFKD").replace(/\p{M}/gu, "");
  }

  function wordsOf(text) {
    return text.split(/[^a-z0-9]+/).filter(Boolean);
  }

  // A text as the matcher reads it: its words and the words run together,
  // in both spellings of an umlaut.
  function piece(text) {
    return [fold(text, false), fold(text, true)].map(folded => {
      const words = wordsOf(folded);
      return { words, joined: words.join("") };
    });
  }

  function queryWords(query) {
    const words = wordsOf(fold(query, false));
    const named = words.filter(word => !FILLERS.has(word));
    return named.length ? named : words;
  }

  // Fewest edits (a letter wrong, missing, extra, or two swapped) that turn
  // `query` into a part of `text`; above `limit` the count stops at limit + 1.
  function editsWithin(query, text, limit) {
    const n = query.length;
    const m = text.length;
    if (m + limit < n) return limit + 1;
    // Row 0 is all zero: the part may start anywhere in the text.
    let before = null;
    let previous = new Array(m + 1).fill(0);
    for (let i = 1; i <= n; i += 1) {
      const row = new Array(m + 1);
      row[0] = i;
      let best = i;
      for (let j = 1; j <= m; j += 1) {
        let edits = Math.min(previous[j] + 1, row[j - 1] + 1,
          previous[j - 1] + (query[i - 1] === text[j - 1] ? 0 : 1));
        if (i > 1 && j > 1 && query[i - 1] === text[j - 2] && query[i - 2] === text[j - 1]) {
          edits = Math.min(edits, before[j - 2] + 1);
        }
        row[j] = edits;
        if (edits < best) best = edits;
      }
      if (best > limit) return limit + 1;
      before = previous;
      previous = row;
    }
    // ...and end anywhere.
    return Math.min(...previous);
  }

  function typoLimit(word) {
    return word.length >= 9 ? 2 : word.length >= 5 ? 1 : 0;
  }

  // How one query word is found in the pieces: EXACT, TYPO or 0.
  function find(word, pieces) {
    const spellings = pieces.flat();
    const exact = spellings.some(({ words, joined }) => (word.length < 4
      ? words.some(each => each.startsWith(word))
      : joined.includes(word)));
    if (exact) return EXACT;
    const limit = typoLimit(word);
    if (!limit) return 0;
    return spellings.some(({ words, joined }) => words.some(each => editsWithin(word, each, limit) <= limit)
      || editsWithin(word, joined, limit) <= limit) ? TYPO : 0;
  }

  // How well the query matches the pieces: EXACT, TYPO or 0 (a word missing).
  function score(words, pieces) {
    let worst = EXACT;
    for (const word of words) {
      const found = find(word, pieces);
      if (!found) return 0;
      worst = Math.min(worst, found);
    }
    return worst;
  }

  // For tests and callers without a DOM: how `query` matches `texts`.
  function matches(query, texts) {
    const words = queryWords(query);
    if (!words.length) return 0;
    return score(words, [].concat(texts).map(piece));
  }

  // --- The dialog -------------------------------------------------------------
  const nodes = {};
  let searching = false;

  function textNodes(root) {
    const found = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: node => (!node.data.trim() || node.parentElement?.closest(NOT_SETTING_TEXT)
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    for (let node = walker.nextNode(); node; node = walker.nextNode()) found.push(node);
    return found;
  }

  function tabFor(panel) {
    return Array.from(document.querySelectorAll("[data-settings-tab]"))
      .find(tab => tab.dataset.settingsTab === panel.id) || null;
  }

  function panels() {
    return Array.from(nodes.body.querySelectorAll(":scope > .settings-category"))
      .filter(panel => !tabFor(panel)?.hidden);
  }

  // Each setting with its words and those of its section (title, keywords).
  function settingsOf(panel) {
    const heading = panel.querySelector(".settings-category-heading h3");
    const shared = [heading?.textContent || "", panel.dataset.settingsKeywords || ""].map(piece);
    return Array.from(panel.querySelectorAll(".settings-group > .settings-section")).map(row => ({
      row,
      pieces: shared.concat(textNodes(row).map(node => piece(node.data)),
        [piece(row.dataset.settingsKeywords || "")]),
    }));
  }

  function setStatus(count) {
    nodes.empty.hidden = count > 0;
    // Whole sentences for singular and plural (docs/i18n.md).
    nodes.status.textContent = count === 0 ? "No setting matches your search."
      : count === 1 ? "1 setting found." : `${count} settings found.`;
  }

  // The query's words where they stand in what is in view, in its own
  // spelling (the folded text is longer where an umlaut is spelled out).
  function tint(words) {
    if (!window.CSS?.highlights || typeof window.Highlight !== "function") return;
    const highlight = new Highlight();
    const visible = nodes.body.querySelectorAll(".settings-category:not([hidden]) .settings-group > .settings-section:not(.is-search-miss)");
    const wanted = words.filter(word => word.length >= 2);
    visible.forEach(row => textNodes(row).forEach(node => {
      const text = node.data.toLowerCase();
      wanted.forEach(word => {
        for (let at = text.indexOf(word); at !== -1; at = text.indexOf(word, at + word.length)) {
          const range = new Range();
          range.setStart(node, at);
          range.setEnd(node, at + word.length);
          highlight.add(range);
        }
      });
    }));
    CSS.highlights.set(HIGHLIGHT, highlight);
  }

  function untint() {
    window.CSS?.highlights?.delete?.(HIGHLIGHT);
  }

  function run(query) {
    if (!nodes.body) return 0;
    const words = queryWords(query || "");
    if (!words.length) {
      exit();
      return 0;
    }
    searching = true;
    nodes.layout.classList.add("is-searching");
    const found = panels().map(panel => ({ panel, settings: settingsOf(panel).map(setting => ({
      ...setting, found: score(words, setting.pieces),
    })) }));
    const all = found.flatMap(entry => entry.settings);
    // A typo match is shown only when nothing matches exactly.
    const best = all.reduce((most, setting) => Math.max(most, setting.found), 0);
    let count = 0;
    nodes.body.querySelectorAll(":scope > .settings-category").forEach(panel => { panel.hidden = true; });
    found.forEach(({ panel, settings }) => {
      const shown = settings.filter(setting => best && setting.found === best);
      settings.forEach(setting => setting.row.classList.toggle("is-search-miss", !shown.includes(setting)));
      panel.querySelectorAll(".settings-group").forEach(group => {
        group.classList.toggle("is-search-miss", !group.querySelector(":scope > .settings-section:not(.is-search-miss)"));
      });
      panel.hidden = !shown.length;
      count += shown.length;
    });
    nodes.body.scrollTop = 0;
    setStatus(count);
    tint(String(query).toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(word => word && !FILLERS.has(fold(word, false))));
    return count;
  }

  // Back to the tabs: the section that was selected (or the one just picked).
  function exit() {
    if (!searching) return;
    searching = false;
    nodes.layout.classList.remove("is-searching");
    nodes.body.querySelectorAll(".is-search-miss").forEach(node => node.classList.remove("is-search-miss"));
    nodes.empty.hidden = true;
    nodes.status.textContent = "";
    untint();
    const selected = document.querySelector(".settings-nav-item.is-active");
    App.settingsTabs?.activate(selected?.dataset.settingsTab || null);
  }

  function clear() {
    if (nodes.input) nodes.input.value = "";
    exit();
  }

  // Enter goes to the first setting found.
  function focusFirst() {
    const row = nodes.body.querySelector(".settings-category:not([hidden]) .settings-group > .settings-section:not(.is-search-miss)");
    const control = row?.querySelector("input:not([type='hidden']), select, textarea, button, [tabindex='0']");
    control?.focus();
  }

  function bind() {
    nodes.input = document.getElementById("settingsSearch");
    nodes.body = document.querySelector(".settings-body");
    nodes.layout = document.querySelector(".settings-layout");
    nodes.empty = document.getElementById("settingsSearchEmpty");
    nodes.status = document.getElementById("settingsSearchStatus");
    const nav = document.querySelector(".settings-nav");
    if (!nodes.input || !nodes.body || !nodes.layout || !nodes.empty || !nodes.status || nodes.input.dataset.bound) return;
    nodes.input.dataset.bound = "true";
    nodes.input.addEventListener("input", () => run(nodes.input.value));
    nodes.input.addEventListener("keydown", event => {
      if (event.key === "Escape" && nodes.input.value) {
        // Clears the field; a second Escape closes Settings (modal-dialog.js
        // leaves a prevented Escape alone).
        event.preventDefault();
        clear();
      } else if (event.key === "Enter") {
        event.preventDefault();
        focusFirst();
      }
    });
    // Picking a section ends the search first; the tabs then show it.
    nav?.addEventListener("click", event => {
      if (searching && event.target.closest("[data-settings-tab]")) clear();
    }, true);
    nav?.addEventListener("keydown", event => {
      // A letter typed on the tabs goes into the search.
      if (event.key.length === 1 && event.key !== " " && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        nodes.input.focus();
        nodes.input.value += event.key;
        run(nodes.input.value);
      } else if (searching && ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Home", "End"].includes(event.key)) {
        clear();
      }
    }, true);
  }

  App.settingsSearch = { matches, run, clear, active: () => searching };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();

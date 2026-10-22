/**
 * settings-search.js -- the search field of Settings: what finds a setting
 * (word parts, typos, umlauts, keywords) and how the dialog shows the hits.
 */

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// The dialog's structure (templates/index.html), shortened. The Agent tab is
// hidden, as for an account without Agent; Memory holds a saved memory.
const DIALOG = `
<div class="settings-layout">
  <div class="settings-side">
    <div class="settings-search"><input type="search" id="settingsSearch"></div>
    <div class="settings-nav" role="tablist">
      <button type="button" class="settings-nav-item is-active" data-settings-tab="displayPanel">Display</button>
      <button type="button" class="settings-nav-item" data-settings-tab="connectionsPanel">Connections</button>
      <button type="button" class="settings-nav-item" data-settings-tab="memoryPanel">Memory</button>
      <button type="button" class="settings-nav-item" data-settings-tab="agentPanel" hidden>Agent</button>
    </div>
  </div>
  <div class="settings-body">
    <p id="settingsSearchEmpty" hidden>No setting matches your search.</p>
    <p id="settingsSearchStatus" role="status"></p>
    <section id="displayPanel" class="settings-category" data-settings-keywords="darstellung display">
      <div class="settings-category-heading"><h3>Display</h3><p>How the app looks.</p></div>
      <div class="settings-group">
        <div class="settings-section" id="theme" data-settings-keywords="dunkel dark theme nachtmodus">
          <h4>Appearance</h4><p>Switch between light and dark mode.</p><button type="button" id="themeToggle">Theme</button>
        </div>
        <div class="settings-section" id="letters" data-settings-keywords="animation bewegung">
          <label><span><strong>Letter animations</strong><small>Letters fade in there while an answer is written.</small></span>
          <input type="checkbox" id="lettersSwitch"></label>
        </div>
      </div>
    </section>
    <section id="connectionsPanel" class="settings-category" data-settings-keywords="verbindungen" hidden>
      <div class="settings-category-heading"><h3>Connections</h3></div>
      <div class="settings-group">
        <div class="settings-section" id="keys" data-settings-keywords="api schlüssel key">
          <label><strong>Use your own API keys</strong><input type="checkbox" id="keysSwitch"></label>
        </div>
      </div>
    </section>
    <section id="memoryPanel" class="settings-category" hidden>
      <div class="settings-category-heading"><h3>Gedächtnis</h3></div>
      <div class="settings-group">
        <div class="settings-section" id="memories"><h4>Saved memories</h4><ul><li>Big fan of opera</li></ul>
          <span role="status">Saved just now</span></div>
      </div>
      <details class="settings-note"><summary>How it works</summary></details>
    </section>
    <section id="agentPanel" class="settings-category" hidden>
      <div class="settings-category-heading"><h3>Agent</h3></div>
      <div class="settings-group"><div class="settings-section" id="depth"><strong>Answer depth</strong><small>secret</small></div></div>
    </section>
  </div>
</div>`;

// App.settingsTabs as app-ui.js has it: one panel at a time, a click on a
// tab selects it.
function boot({ highlights = true } = {}) {
  const loaded = loadScripts(["static/js/settings-search.js"], {
    body: DIALOG,
    before(window) {
      const { document } = window;
      const tabs = () => [...document.querySelectorAll("[data-settings-tab]")];
      const activated = [];
      const activate = id => {
        activated.push(id);
        const target = tabs().find(tab => tab.dataset.settingsTab === id && !tab.hidden) || tabs().find(tab => !tab.hidden);
        tabs().forEach(tab => {
          tab.classList.toggle("is-active", tab === target);
          document.getElementById(tab.dataset.settingsTab).hidden = tab !== target;
        });
      };
      window.App = { settingsTabs: { activate, activated } };
      document.querySelector(".settings-nav").addEventListener("click", event => {
        const tab = event.target.closest("[data-settings-tab]");
        if (tab) activate(tab.dataset.settingsTab);
      });
      if (highlights) {
        window.Highlight = class extends window.Set {};
        window.CSS = { highlights: new Map() };
      }
    },
  });
  const { window, document } = loaded;
  // jsdom is still "loading" here; the module binds on DOMContentLoaded.
  document.dispatchEvent(new window.Event("DOMContentLoaded"));
  const input = document.getElementById("settingsSearch");
  const type = text => {
    input.value = text;
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
  };
  const press = (target, key) => target.dispatchEvent(new window.KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
  // The settings in view: visible panel, not a miss.
  const shown = () => [...document.querySelectorAll(".settings-category:not([hidden]) .settings-group > .settings-section:not(.is-search-miss)")]
    .map(row => row.id);
  return { ...loaded, search: window.App.settingsSearch, input, type, press, shown, tabs: window.App.settingsTabs };
}

describe("settings search: what finds a setting", () => {
  const { search } = boot();

  it("finds the start of a word, and from four letters any part of one", () => {
    expect(search.matches("anim", "Letter animations")).toBe(2);
    expect(search.matches("prompt", "Systemprompt")).toBe(2);
    expect(search.matches("sta", "start")).toBe(2);
    // Three letters inside a word are too little to mean it.
    expect(search.matches("art", "start")).toBe(0);
  });

  it("finds a word that runs on over a hyphen or a space", () => {
    expect(search.matches("buchstabenanimation", "Buchstaben-Animationen")).toBe(2);
    expect(search.matches("darkmode", "dark mode")).toBe(2);
  });

  it("forgives a typo from five letters on, two from nine, and says it was one", () => {
    expect(search.matches("animaton", "Letter animations")).toBe(1);
    expect(search.matches("sprahce", "Sprache")).toBe(1);
    expect(search.matches("einstelungen", "Einstellungen")).toBe(1);
    expect(search.matches("ainmatoin", "animation")).toBe(1);
    // Four letters are too short for a guess: "drak" is no "dark".
    expect(search.matches("drak", "dark")).toBe(0);
    expect(search.matches("zebra", "Letter animations")).toBe(0);
  });

  it("matches umlauts spelled out and plain", () => {
    expect(search.matches("gedächtnis", "Gedächtnis")).toBe(2);
    expect(search.matches("gedaechtnis", "Gedächtnis")).toBe(2);
    expect(search.matches("gedachtnis", "Gedächtnis")).toBe(2);
    expect(search.matches("strasse", "Straße")).toBe(2);
  });

  it("needs every word of the query, but not its filler words", () => {
    expect(search.matches("dark api", ["dark mode"])).toBe(0);
    expect(search.matches("dark api", ["dark mode", "API key"])).toBe(2);
    expect(search.matches("animationen aus", "Animationen")).toBe(2);
    expect(search.matches("turn off the animations", "animations")).toBe(0);
    // A query of filler words only is searched as it is.
    expect(search.matches("aus", "Aus")).toBe(2);
  });
});

describe("settings search: the dialog", () => {
  it("shows the matching settings of every section and nothing else", () => {
    const app = boot();
    app.type("dunkel");
    expect(app.shown()).toEqual(["theme"]);
    expect(app.document.querySelector(".settings-layout").classList.contains("is-searching")).toBe(true);
    expect(app.document.getElementById("settingsSearchStatus").textContent).toBe("1 setting found.");

    // A section whose tab was not selected shows its hits as well.
    app.type("schlüssel");
    expect(app.shown()).toEqual(["keys"]);
    expect(app.document.getElementById("displayPanel").hidden).toBe(true);
  });

  it("shows a whole section when the query names it", () => {
    const app = boot();
    app.type("darstellung");
    expect(app.shown()).toEqual(["theme", "letters"]);
    app.type("display dark");
    expect(app.shown()).toEqual(["theme"]);
  });

  it("shows typo matches only when nothing matches exactly", () => {
    const app = boot();
    // "theme" is a keyword of Appearance; "there" in the letters text is a typo away.
    app.type("theme");
    expect(app.shown()).toEqual(["theme"]);
    app.type("animaton");
    expect(app.shown()).toEqual(["letters"]);
  });

  it("never searches a hidden tab's section, saved memories or status lines", () => {
    const app = boot();
    for (const query of ["secret", "opera", "just now"]) {
      app.type(query);
      expect(app.shown()).toEqual([]);
    }
    expect(app.document.getElementById("settingsSearchEmpty").hidden).toBe(false);
    expect(app.document.getElementById("settingsSearchStatus").textContent).toBe("No setting matches your search.");
    expect(app.document.getElementById("agentPanel").hidden).toBe(true);
  });

  it("tints the words found and drops the tint with the search", () => {
    const app = boot();
    app.type("dark");
    const ranges = [...app.window.CSS.highlights.get("settings-search")];
    expect(ranges.map(range => range.toString())).toEqual(["dark"]);
    app.type("");
    expect(app.window.CSS.highlights.has("settings-search")).toBe(false);
  });

  it("goes back to the selected tab when the field is cleared or Escape pressed", () => {
    const app = boot();
    app.type("schlüssel");
    expect(app.press(app.input, "Escape")).toBe(false);
    expect(app.input.value).toBe("");
    expect(app.document.querySelector(".settings-layout").classList.contains("is-searching")).toBe(false);
    expect(app.document.querySelectorAll(".is-search-miss")).toHaveLength(0);
    expect(app.tabs.activated.at(-1)).toBe("displayPanel");
    expect(app.document.getElementById("displayPanel").hidden).toBe(false);
    expect(app.document.getElementById("connectionsPanel").hidden).toBe(true);
    // An empty field leaves Escape to the dialog.
    expect(app.press(app.input, "Escape")).toBe(true);
  });

  it("ends the search when a tab is picked, and shows that tab", () => {
    const app = boot();
    app.type("dunkel");
    app.document.querySelector("[data-settings-tab='connectionsPanel']").click();
    expect(app.input.value).toBe("");
    expect(app.search.active()).toBe(false);
    expect(app.document.getElementById("connectionsPanel").hidden).toBe(false);
    expect(app.document.getElementById("displayPanel").hidden).toBe(true);
  });

  it("goes to the first setting found on Enter", () => {
    const app = boot();
    app.type("animation");
    app.press(app.input, "Enter");
    expect(app.document.activeElement.id).toBe("lettersSwitch");
  });

  it("takes a letter typed on the tabs into the field", () => {
    const app = boot();
    const tab = app.document.querySelector("[data-settings-tab='displayPanel']");
    app.press(tab, "a");
    expect(app.document.activeElement).toBe(app.input);
    expect(app.input.value).toBe("a");
    expect(app.search.active()).toBe(true);
  });

  it("clear() empties the field for the next opening", () => {
    const app = boot();
    app.type("dark");
    app.search.clear();
    expect(app.input.value).toBe("");
    expect(app.search.active()).toBe(false);
  });
});

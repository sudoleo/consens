/**
 * app-init.js -- der Start von /app, wenn localStorage nicht mitspielt.
 *
 * Bei gesperrtem Speicher (blockierte Cookies, manche privaten Modi) wirft
 * schon der ZUGRIFF auf window.localStorage. Ein einziger ungeschuetzter
 * Lesezugriff in initApp brach den ganzen Start ab: Theme, Sidebar,
 * Bookmarks, Tooltips blieben unverdrahtet. Geladen werden deshalb die echten
 * Klassik-Skripte von /app (Gruppen head + app aus bundles.json) in ihrer
 * Ladereihenfolge - nicht app-init.js allein mit Attrappen.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

const bundles = JSON.parse(readFileSync(path.join(ROOT, "static/js/bundles.json"), "utf8"));
const APP_SCRIPTS = bundles.groups
  .filter((group) => group.kind === "classic" && ["head", "app"].includes(group.name))
  .flatMap((group) => group.files.map((entry) => (typeof entry === "string" ? entry : entry.file)));

// Nur die Stellen aus templates/index.html, die initApp ohne "?." anfasst
// oder die hier geprueft werden.
const APP_MARKUP = `
  <button id="toggleSidebarButton" class="sidebar-toggle" type="button"></button>
  <aside class="sidebar">
    <div class="bookmarks-section">
      <button id="bookmarksToggle" type="button" aria-expanded="true"></button>
      <div id="bookmarksContainer"></div>
    </div>
  </aside>
  <a id="logoLink" href="#home"></a>
  <button class="theme-toggle" type="button"></button>
  <button id="reasoningToggle" type="button"></button>
  <button id="feedbackButton" type="button"></button>
  <div id="feedbackModal"><button id="closeFeedbackModal" type="button"></button></div>
  <textarea id="questionInput"></textarea>
  <button id="sendButton" type="button"></button>
  <input id="openrouterKey">
`;

async function bootApp({ storage = {}, prefersDark = false } = {}) {
  const errors = [];
  const media = { prefersDark, narrow: false };
  const loaded = loadScripts(APP_SCRIPTS, {
    body: APP_MARKUP,
    before(window) {
      window.addEventListener("error", (event) => errors.push(event.error || event.message));
      if (storage === "blocked") {
        Object.defineProperty(window, "localStorage", {
          configurable: true,
          get() { throw new window.DOMException("The operation is insecure.", "SecurityError"); },
        });
      } else {
        Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      }
      window.matchMedia = (query) => ({
        media: query,
        matches: query.includes("prefers-color-scheme: dark") ? media.prefersDark
          : query.includes("max-width") ? media.narrow : false,
        addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
      });
      window.fetch = () => new Promise(() => {});
      // jsdom zeichnet nicht; ohne Kontext bleibt letter-clouds.js still,
      // statt bei jedem Aufruf „Not implemented“ nach stderr zu schreiben.
      window.HTMLCanvasElement.prototype.getContext = () => null;
      // Kommt aus static/demo.js (ES-Modul, hier nicht geladen).
      window.createStartDemoChip = () => { window.demoChipShown = true; };
    },
  });
  // initApp startet mit DOMContentLoaded, genau wie im Browser.
  if (loaded.document.readyState === "loading") {
    await new Promise((resolve) => loaded.document.addEventListener("DOMContentLoaded", resolve));
  }
  return { ...loaded, errors, media };
}

// Beobachter (MutationObserver, Timer) der Module laufen nach dem Klick;
// erst danach ist sicher, dass auch sie nichts geworfen haben.
function settle(window) {
  return new Promise((resolve) => window.setTimeout(resolve, 0));
}

function storedValue(window, key) {
  return window.localStorage.getItem(key);
}

describe("app-init.js mit gesperrtem localStorage", () => {
  it("startet vollstaendig, obwohl schon der Zugriff auf localStorage wirft", async () => {
    const { window, document, errors } = await bootApp({ storage: "blocked", prefersDark: true });

    expect(errors).toEqual([]);
    // Der Tooltip ist das Letzte, was initApp anlegt.
    expect(document.querySelector(".global-tooltip")).not.toBeNull();
    expect(document.body.classList.contains("dark-mode")).toBe(true);
    expect(window.demoChipShown).toBe(true);

    document.querySelector(".theme-toggle").click();
    expect(document.body.classList.contains("dark-mode")).toBe(false);

    window.toggleBookmarks();
    expect(document.querySelector(".bookmarks-section").classList.contains("is-collapsed")).toBe(true);

    document.getElementById("logoLink").click();
    await settle(window);
    expect(errors).toEqual([]);
    window.close();
  });

  it("haelt die Sidebar-Wahl fuer diese Seite, wenn der Speicher sie verweigert", async () => {
    const { window, document, errors, media } = await bootApp({ storage: "blocked" });
    const sidebar = document.querySelector(".sidebar");

    document.getElementById("toggleSidebarButton").click();
    expect(sidebar.classList.contains("collapsed")).toBe(true);

    // Ueber das Overlay-Layout und zurueck: die Wahl liest sich neu ein.
    media.narrow = true;
    window.dispatchEvent(new window.Event("resize"));
    media.narrow = false;
    window.dispatchEvent(new window.Event("resize"));
    expect(sidebar.classList.contains("collapsed")).toBe(true);
    await settle(window);
    expect(errors).toEqual([]);
    window.close();
  });
});

describe("app-init.js mit funktionierendem localStorage", () => {
  it("liest die gespeicherten Werte wie bisher", async () => {
    const { window, document, errors } = await bootApp({
      storage: {
        theme: "dark",
        sidebar_collapsed: "true",
        bookmarks_collapsed: "true",
        openrouterKey: "test-openrouter-key",
        marketingPopupShown: "true",
        demoChipDismissed: "true",
      },
    });

    expect(errors).toEqual([]);
    expect(document.body.classList.contains("dark-mode")).toBe(true);
    expect(document.querySelector(".sidebar").classList.contains("collapsed")).toBe(true);
    expect(document.querySelector(".bookmarks-section").classList.contains("is-collapsed")).toBe(true);
    expect(document.getElementById("bookmarksContainer").classList.contains("hidden")).toBe(true);
    expect(document.getElementById("openrouterKey").value).toBe("test-openrouter-key");
    expect(window.demoChipShown).toBeUndefined();
    window.close();
  });

  it("schreibt Theme, Sidebar, Bookmarks und Landing-Marke wie bisher", async () => {
    const { window, document, errors } = await bootApp({
      storage: { visitedLanding: "true" },
      prefersDark: true,
    });

    // Ohne gespeichertes Theme gilt die Systempraeferenz und wird gemerkt.
    expect(storedValue(window, "theme")).toBe("dark");
    document.querySelector(".theme-toggle").click();
    expect(storedValue(window, "theme")).toBe("light");

    document.getElementById("toggleSidebarButton").click();
    expect(storedValue(window, "sidebar_collapsed")).toBe("true");

    window.toggleBookmarks();
    expect(storedValue(window, "bookmarks_collapsed")).toBe("true");

    document.getElementById("logoLink").click();
    expect(storedValue(window, "visitedLanding")).toBeNull();

    window.App.restoreQuestionDraft();
    expect(document.getElementById("questionInput").value).toBe("");
    window.localStorage.setItem("consensio.questionDraft.v1", "Was kostet das?");
    window.App.restoreQuestionDraft();
    expect(document.getElementById("questionInput").value).toBe("Was kostet das?");
    window.App.clearQuestionDraft();
    expect(storedValue(window, "consensio.questionDraft.v1")).toBeNull();

    // A guest's draft is kept whole (a pasted answer to check is long) and
    // only for a day.
    const long = "x".repeat(6000);
    window.App.saveQuestionDraft(long);
    document.getElementById("questionInput").value = "";
    window.App.restoreQuestionDraft();
    expect(document.getElementById("questionInput").value).toBe(long);
    window.localStorage.setItem("consensio.questionDraft.v1",
      JSON.stringify({ text: "Old", at: Date.now() - 25 * 60 * 60 * 1000 }));
    document.getElementById("questionInput").value = "";
    window.App.restoreQuestionDraft();
    expect(document.getElementById("questionInput").value).toBe("");
    expect(storedValue(window, "consensio.questionDraft.v1")).toBeNull();

    await settle(window);
    expect(errors).toEqual([]);
    window.close();
  });
});

/**
 * app-init.js -- Escape in the open sidebar drawer (up to 1099 px).
 *
 * The drawer closes on a plain Escape (capture handler on window), but what
 * lives in it takes its own Escape first: the chat search clears and closes
 * itself, and only the next Escape closes the drawer (bug hunt 2026-10-30,
 * app-init.js:644: the search's Escape closed the whole drawer).
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

const bundles = JSON.parse(readFileSync(path.join(ROOT, "static/js/bundles.json"), "utf8"));
const APP_SCRIPTS = bundles.groups
  .filter((group) => group.kind === "classic" && ["head", "auth", "app"].includes(group.name))
  .flatMap((group) => group.files.map((entry) => (typeof entry === "string" ? entry : entry.file)))
  .filter((file) => !file.endsWith("auth-bootstrap.js"));

const APP_MARKUP = `
  <button id="toggleSidebarButton" class="sidebar-toggle" type="button"></button>
  <aside id="appSidebar" class="sidebar">
    <button id="sidebarToggleInner" class="sidebar-toggle" type="button"></button>
    <div class="bookmarks-section">
      <div class="sidebar-bookmarks-head">
        <button id="bookmarksToggle" type="button" aria-expanded="true"></button>
        <button id="bookmarkSearchTrigger" type="button" aria-expanded="false"></button>
        <input id="chatSearch" type="search">
      </div>
      <div id="bookmarksContainer"></div>
    </div>
  </aside>
  <div class="container"><a id="logoLink" href="#home"></a></div>
  <button class="theme-toggle" type="button"></button>
  <button id="reasoningToggle" type="button"></button>
  <button id="feedbackButton" type="button"></button>
  <div id="feedbackModal"><button id="closeFeedbackModal" type="button"></button></div>
  <textarea id="questionInput"></textarea>
  <button id="sendButton" type="button"></button>
  <input id="openrouterKey">
`;

async function bootNarrowApp() {
  const errors = [];
  const loaded = loadScripts(APP_SCRIPTS, {
    body: APP_MARKUP,
    before(window) {
      window.addEventListener("error", (event) => errors.push(event.error || event.message));
      window.matchMedia = (query) => ({
        media: query,
        matches: query.includes("max-width"),
        addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
      });
      window.fetch = () => new Promise(() => {});
      window.HTMLCanvasElement.prototype.getContext = () => null;
      window.createStartDemoChip = () => {};
    },
  });
  if (loaded.document.readyState === "loading") {
    await new Promise((resolve) => loaded.document.addEventListener("DOMContentLoaded", resolve));
  }
  return { ...loaded, errors };
}

function escape(window, target) {
  target.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
}

describe("Escape in the sidebar drawer", () => {
  it("closes the chat search first and the drawer only on the next Escape", async () => {
    const { window, document, errors } = await bootNarrowApp();
    const sidebar = document.querySelector(".sidebar");
    window.filterBookmarks = () => {};
    document.getElementById("toggleSidebarButton").click();
    expect(sidebar.classList.contains("active")).toBe(true);

    document.getElementById("bookmarkSearchTrigger").click();
    const search = document.getElementById("chatSearch");
    search.focus();
    search.value = "budget";
    expect(document.querySelector(".sidebar-bookmarks-head").classList.contains("is-searching")).toBe(true);

    escape(window, search);
    expect(sidebar.classList.contains("active")).toBe(true);
    expect(search.value).toBe("");
    expect(document.querySelector(".sidebar-bookmarks-head").classList.contains("is-searching")).toBe(false);
    expect(document.activeElement.id).toBe("bookmarksToggle");

    escape(window, document.activeElement);
    expect(sidebar.classList.contains("active")).toBe(false);
    expect(errors).toEqual([]);
    window.close();
  });
});

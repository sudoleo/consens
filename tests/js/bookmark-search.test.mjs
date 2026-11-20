/**
 * Bookmark search in the sidebar.
 *
 * The first non-empty term loads the remaining bookmark metadata pages before
 * it filters. The handler reads the field after that await: filtering by the
 * term read BEFORE it, a slow first load finishing after the person had typed
 * on left the list filtered by an older term.
 */

import { describe, expect, it, vi } from "vitest";

import { bootApp, settle } from "./helpers/appBoot.mjs";

const BODY = `
  <button id="toggleSidebarButton" class="sidebar-toggle" type="button"></button>
  <aside class="sidebar">
    <div class="sidebar-head">
      <button id="newRunButton" type="button"></button>
      <button id="bookmarkSearchTrigger" type="button" aria-expanded="false"></button>
      <button id="sidebarToggleInner" type="button"></button>
      <div class="sidebar-search-box"><input id="chatSearch" type="search"></div>
    </div>
    <div class="sidebar-section bookmarks-section">
      <div id="bookmarksContainer">
        <div class="bookmark" data-id="a"><p>Alpha question</p></div>
        <div class="bookmark" data-id="b"><p>Beta question</p></div>
        <div class="bookmark" data-id="c"><p>Alphabet soup</p></div>
      </div>
    </div>
  </aside>
  <input id="reasoningToggle" type="checkbox">
  <textarea id="questionInput"></textarea>
  <button id="sendButton" type="button"></button>
  <input id="openrouterKey">
`;

function visibleIds(document) {
  return Array.from(document.querySelectorAll("#bookmarksContainer .bookmark"))
    .filter((row) => row.style.display !== "none")
    .map((row) => row.dataset.id);
}

function type(window, input, value) {
  input.value = value;
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
}

describe("bookmark search", () => {
  it("filters by the current term after a slow metadata load, not by the term it started with", async () => {
    const { window, document, errors } = await bootApp({ body: BODY });
    let finishFirstLoad;
    const firstLoad = new Promise((resolve) => { finishFirstLoad = resolve; });
    window.loadAllBookmarkMetadata = vi.fn()
      .mockReturnValueOnce(firstLoad)
      .mockResolvedValue(undefined);
    const input = document.getElementById("chatSearch");

    type(window, input, "alpha");
    type(window, input, "beta");
    await settle(window);
    expect(visibleIds(document)).toEqual(["b"]);

    // The first, slow load finishes last. Its handler must not bring back
    // the "alpha" filter the person has already typed past.
    finishFirstLoad();
    await settle(window);
    expect(visibleIds(document)).toEqual(["b"]);
    expect(errors).toEqual([]);
    window.close();
  });

  it("shows every row again when the field is cleared while a load is pending", async () => {
    const { window, document } = await bootApp({ body: BODY });
    let finishLoad;
    window.loadAllBookmarkMetadata = vi.fn(() => new Promise((resolve) => { finishLoad = resolve; }));
    const input = document.getElementById("chatSearch");

    type(window, input, "alpha");
    type(window, input, "");
    expect(visibleIds(document)).toEqual(["a", "b", "c"]);
    finishLoad();
    await settle(window);
    expect(visibleIds(document)).toEqual(["a", "b", "c"]);
    window.close();
  });

  // The field lies over New chat's row. Left empty it must give the row
  // back when the focus goes on, also to the panel glyph in the same head;
  // with a term in it the filtered list keeps its field.
  it("gives the head's row back when the focus leaves an empty field, and keeps a term", async () => {
    const { window, document } = await bootApp({ body: BODY });
    window.loadAllBookmarkMetadata = vi.fn().mockResolvedValue(undefined);
    const head = document.querySelector(".sidebar-head");
    const trigger = document.getElementById("bookmarkSearchTrigger");
    const input = document.getElementById("chatSearch");
    const leave = async () => {
      document.getElementById("sidebarToggleInner").focus();
      await new Promise(resolve => window.setTimeout(resolve, 0));
    };

    trigger.click();
    input.focus();
    expect(head.classList.contains("is-searching")).toBe(true);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    await leave();
    expect(head.classList.contains("is-searching")).toBe(false);
    expect(trigger.getAttribute("aria-expanded")).toBe("false");

    trigger.click();
    input.focus();
    type(window, input, "alpha");
    await settle(window);
    await leave();
    expect(head.classList.contains("is-searching")).toBe(true);
    expect(visibleIds(document)).toEqual(["a", "c"]);
    window.close();
  });

  // On a Mac, Ctrl+K deletes to the end of the line in any text field; the
  // search took it, in the rename field with half a name saved.
  it.each([
    ["MacIntel", { metaKey: true }, { ctrlKey: true }, "Meta+K"],
    ["Win32", { ctrlKey: true }, { metaKey: true }, "Control+K"],
  ])("opens the search with the platform's own shortcut only (%s)", async (platform, own, other, keys) => {
    const { window, document } = await bootApp({ body: BODY, before(w) {
      Object.defineProperty(w.navigator, "platform", { configurable: true, get: () => platform });
    } });
    const field = document.getElementById("questionInput");
    const press = init => {
      field.focus();
      const event = new window.KeyboardEvent("keydown", { key: "k", bubbles: true, cancelable: true, ...init });
      field.dispatchEvent(event);
      return event;
    };
    expect(document.getElementById("bookmarkSearchTrigger").getAttribute("aria-keyshortcuts")).toBe(keys);
    expect(press(other).defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(field);
    expect(press(own).defaultPrevented).toBe(true);
    window.close();
  });
});

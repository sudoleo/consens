/**
 * Settings, Help and Feedback as real dialogs (audit F3, F5).
 *
 * The three windows used to be <div>s that a click set to display:block:
 * no dialog role, no Escape, no focus handling, a <span> as close button,
 * and a backdrop listener on window that also fired when a text selection
 * started in a field and ended over the backdrop. They are native <dialog>s
 * now, opened through App.modalDialog. The markup is cut from
 * templates/index.html and the real /app scripts run in their load order.
 *
 * jsdom has HTMLDialogElement but no showModal(), so the helper's fallback
 * path runs here; one test stubs showModal/close like a browser to cover the
 * native path (close event, focus restore).
 */

import { describe, expect, it } from "vitest";

import { bootApp, settle, templateSlice } from "./helpers/appBoot.mjs";

const SIDEBAR = `
  <button id="toggleSidebarButton" class="sidebar-toggle" type="button"></button>
  <aside class="sidebar">
    <div class="bookmarks-section"><button id="bookmarksToggle" type="button"></button><div id="bookmarksContainer"></div></div>
    <button id="editSystemPromptBtn" type="button" aria-label="Settings">Settings</button>
    <button type="button" id="feedbackButton" aria-label="Send feedback">Feedback</button>
  </aside>
  <a id="logoLink" href="#home"></a>
  <input id="reasoningToggle" type="checkbox">
  <textarea id="questionInput"></textarea>
  <button id="sendButton" type="button"></button>
  <input id="openrouterKey">
`;

const DIALOGS = templateSlice('id="feedbackModal"', "</dialog>")
  + templateSlice('id="popupContainer"', "</dialog>\n  </div>");

function boot(options = {}) {
  return bootApp({ body: SIDEBAR + DIALOGS, ...options });
}

function key(document, target, name, init = {}) {
  const event = new document.defaultView.KeyboardEvent("keydown", {
    key: name, bubbles: true, cancelable: true, ...init,
  });
  target.dispatchEvent(event);
  return event;
}

function pointer(window, target, type) {
  target.dispatchEvent(new window.MouseEvent(type, { bubbles: true, cancelable: true }));
}

describe("dialog markup", () => {
  it("names each dialog and gives it a real close button", async () => {
    const { document, errors, window } = await boot();
    for (const [id, title] of [
      ["systemPromptModal", "Settings"],
      ["helpModal", "FAQ & Quick Start"],
      ["feedbackModal", "Send Feedback"],
    ]) {
      const dialog = document.getElementById(id);
      expect(dialog.tagName).toBe("DIALOG");
      const label = document.getElementById(dialog.getAttribute("aria-labelledby"));
      expect(label?.textContent.trim()).toBe(title);
      const close = dialog.querySelector(".close");
      expect(close.tagName).toBe("BUTTON");
      expect(close.getAttribute("type")).toBe("button");
      expect(close.getAttribute("aria-label")).toMatch(/^Close /);
    }
    // Help is no longer nested in Settings: closing one must not hide the other.
    expect(document.getElementById("systemPromptModal").contains(document.getElementById("helpModal"))).toBe(false);
    expect(errors).toEqual([]);
    window.close();
  });
});

describe("Settings and Help", () => {
  it("opens Settings on the first tab, closes on Escape and returns focus to the gear", async () => {
    const { document, window, errors } = await boot();
    const gear = document.getElementById("editSystemPromptBtn");
    const settings = document.getElementById("systemPromptModal");

    gear.focus();
    gear.click();
    expect(settings.open).toBe(true);
    expect(document.activeElement).toBe(document.getElementById("settingsTabMemory"));
    expect(document.activeElement.getAttribute("aria-selected")).toBe("true");

    const escape = key(document, document.activeElement, "Escape");
    expect(escape.defaultPrevented).toBe(true);
    expect(settings.open).toBe(false);
    expect(document.activeElement).toBe(gear);
    expect(errors).toEqual([]);
    window.close();
  });

  it("keeps an Escape inside Settings away from document-level handlers behind it", async () => {
    const { document, window } = await boot();
    let behind = 0;
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") behind += 1; });
    document.getElementById("editSystemPromptBtn").click();
    key(document, document.getElementById("systemPromptInput"), "Escape");
    expect(behind).toBe(0);
    expect(document.getElementById("systemPromptModal").open).toBe(false);
    window.close();
  });

  it("stacks Help over Settings: Escape closes Help first and focus returns to the ? button", async () => {
    const { document, window } = await boot();
    const settings = document.getElementById("systemPromptModal");
    const help = document.getElementById("helpModal");
    const helpButton = document.getElementById("helpButton");

    document.getElementById("editSystemPromptBtn").click();
    helpButton.focus();
    helpButton.click();
    expect(help.open).toBe(true);
    expect(help.contains(document.activeElement)).toBe(true);

    key(document, document.activeElement, "Escape");
    expect(help.open).toBe(false);
    expect(settings.open).toBe(true);
    expect(document.activeElement).toBe(helpButton);

    document.getElementById("closeSystemPromptModal").click();
    expect(settings.open).toBe(false);
    window.close();
  });

  it("keeps the overlay sidebar open behind Settings, so focus can return to the gear", async () => {
    // Below 1100px the sidebar is an overlay that a click elsewhere closes.
    // A click inside the dialog it opened is not "elsewhere".
    const { document, window } = await boot({ media: { "max-width": true } });
    const sidebar = document.querySelector(".sidebar");
    const gear = document.getElementById("editSystemPromptBtn");
    document.getElementById("toggleSidebarButton").click();
    expect(sidebar.classList.contains("active")).toBe(true);

    gear.focus();
    gear.click();
    document.getElementById("settingsTabBehavior").click();
    document.getElementById("closeSystemPromptModal").click();
    expect(sidebar.classList.contains("active")).toBe(true);
    expect(document.activeElement).toBe(gear);

    // A click on the page itself still closes the overlay sidebar.
    document.getElementById("logoLink").dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
    expect(sidebar.classList.contains("active")).toBe(false);
    window.close();
  });

  it("does not close when a text selection ends over the backdrop (F5)", async () => {
    const { document, window } = await boot();
    const settings = document.getElementById("systemPromptModal");
    const field = document.getElementById("systemPromptInput");

    document.getElementById("editSystemPromptBtn").click();
    field.value = "An edit that is not saved yet";
    // Press inside the field, release over the backdrop: the browser fires
    // the click on the common ancestor, the dialog itself.
    pointer(window, field, "pointerdown");
    pointer(window, settings, "click");
    expect(settings.open).toBe(true);
    expect(field.value).toBe("An edit that is not saved yet");

    // A deliberate click on the backdrop still closes it.
    pointer(window, settings, "pointerdown");
    pointer(window, settings, "click");
    expect(settings.open).toBe(false);
    window.close();
  });

  it("uses showModal() and restores focus on the close event, as a browser does", async () => {
    const { document, window } = await boot({
      before(window) {
        const proto = window.HTMLDialogElement.prototype;
        proto.showModal = function showModal() { this.setAttribute("open", ""); this.dataset.modal = "true"; };
        proto.close = function close() {
          if (!this.hasAttribute("open")) return;
          this.removeAttribute("open");
          // A browser queues the close event as a task.
          window.setTimeout(() => this.dispatchEvent(new window.Event("close")), 0);
        };
      },
    });
    const gear = document.getElementById("editSystemPromptBtn");
    const settings = document.getElementById("systemPromptModal");
    gear.focus();
    gear.click();
    expect(settings.dataset.modal).toBe("true");

    // Native Escape: the helper only stops propagation; the browser's own
    // cancel step closes the dialog (simulated by close()).
    const escape = key(document, document.activeElement, "Escape");
    expect(escape.defaultPrevented).toBe(false);
    settings.close();
    document.activeElement.blur();
    await settle(window);
    expect(document.activeElement).toBe(gear);
    window.close();
  });
});

describe("Help content", () => {
  it("makes every FAQ question a keyboard-operable button inside its heading", async () => {
    const { document, window } = await boot();
    const headings = Array.from(document.querySelectorAll("#helpModal .faq-item h3"));
    expect(headings.length).toBeGreaterThan(5);
    for (const heading of headings) {
      const button = heading.querySelector(":scope > button.faq-question");
      expect(button).not.toBeNull();
      expect(button.getAttribute("aria-expanded")).toBe("false");
      expect(document.getElementById(button.getAttribute("aria-controls"))).toBe(heading.nextElementSibling);
    }
    const first = headings[0].querySelector("button");
    first.click();
    expect(first.getAttribute("aria-expanded")).toBe("true");
    expect(headings[0].nextElementSibling.style.display).toBe("block");
    window.close();
  });
});

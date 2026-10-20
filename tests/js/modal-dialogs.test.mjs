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
      ["helpModal", "Help"],
      ["feedbackModal", "Send feedback"],
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

describe("Settings for a guest (Apple-Audit H13)", () => {
  it("says why Memory and the key are greyed out and leads to the login", async () => {
    const opened = [];
    const { document, window } = await boot({
      before(win) {
        win.App = win.App || {};
        win.App.openAuthModal = (mode, trigger, source, options) => opened.push({ mode, trigger, source, lead: options?.lead });
      }
    });
    const note = document.getElementById("settingsGuestNote");
    document.getElementById("editSystemPromptBtn").click();
    expect(note.hidden).toBe(false);
    expect(note.textContent).toContain("kept on your account");
    document.getElementById("settingsLoginButton").click();
    expect(document.getElementById("systemPromptModal").open).toBe(false);
    expect(opened).toEqual([{ mode: "login", trigger: document.getElementById("editSystemPromptBtn"), source: "settings",
      lead: "Log in to keep your memory and settings on your account." }]);
    window.close();
  });

  it("shows no such line to an account", async () => {
    const { document, window } = await boot({ before(win) {
      win.auth = { currentUser: { uid: "u1", emailVerified: true, getIdToken: async () => "token" } };
      win.fetch = async () => ({ ok: false, status: 503, json: async () => ({}) });
    } });
    document.getElementById("editSystemPromptBtn").click();
    expect(document.getElementById("settingsGuestNote").hidden).toBe(true);
    await settle(window);
    window.close();
  });
});

describe("The key test (Apple-Audit H12)", () => {
  function bootWith(respond) {
    return boot({ before(win) {
      win.auth = { currentUser: { uid: "u1", emailVerified: true, getIdToken: async () => "token" } };
      const memory = () => new Promise(() => {});
      win.fetch = async (url, options) => (url === "/check_keys" ? respond() : memory());
    } });
  }

  it("marks a valid key with a check in the agreement colour, never a star", async () => {
    const { document, window } = await bootWith(async () => new Response(JSON.stringify({ results: { OpenRouter: "valid" } }), { status: 200 }));
    document.getElementById("openrouterKey").value = "sk-or-test";
    await window.testAllKeys();
    const verdict = document.getElementById("openrouterFeedback");
    expect(verdict.classList.contains("is-valid")).toBe(true);
    expect(verdict.querySelector("svg path").getAttribute("d")).toBe("M3.5 8.5l3 3 6-7");
    expect(verdict.getAttribute("aria-label")).toBe("Key verified");
    expect(verdict.textContent).not.toMatch(/[☆★✓✗]/);
    expect(verdict.style.color).toBe("");
    expect(document.getElementById("apiKeysStatus").textContent).toBe("Key saved and verified.");
    window.close();
  });

  it("says plainly when the test itself failed, never JSON or the engine's words", async () => {
    const { document, window } = await bootWith(async () => new Response("<html>Bad gateway</html>", { status: 502 }));
    document.getElementById("openrouterKey").value = "sk-or-test";
    await window.testAllKeys();
    const status = document.getElementById("apiKeysStatus").textContent;
    expect(status).toBe("The key couldn’t be tested. consens.io can’t be reached right now. Try again in a moment.");
    expect(document.getElementById("openrouterFeedback").childElementCount).toBe(0);
    window.close();
  });
});

describe("The help (Apple-Audit H7)", () => {
  it("describes the product of today: one answer the models check, Watches, the allowance, memory, data", async () => {
    const { document, window } = await boot();
    const help = document.getElementById("helpModal");
    const questions = [...help.querySelectorAll(".faq-item h3")].map(heading => heading.textContent.replace(/[＋+−]/g, "").replace(/\s+/g, " ").trim());
    expect(questions).toEqual([
      "1. What happens when I send a message?",
      "2. What do the marks in an answer mean?",
      "3. What is a Watch?",
      "4. How much can I use it?",
      "5. What does consens.io remember?",
      "6. What happens to my data?",
    ]);
    expect(help.textContent).not.toMatch(/Auto Consensus|Consensus Button|Consensus Model|login/);
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

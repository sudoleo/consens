import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

/**
 * The layers above the page are one family (Apple audit C1, C4, E1, E6,
 * E10, G1, G3):
 *   - no browser alert()/confirm() outside the admin, no blur anywhere;
 *   - every modal window is a native <dialog> opened through App.modalDialog,
 *     with the one scrim, the one surface and a way in and out;
 *   - exactly one popover is open, and every menu has the same keyboard;
 *   - one drawn close cross.
 */
const read = (relative) => readFileSync(path.join(ROOT, relative), "utf8").replace(/\r\n/g, "\n");

function files(dir, extensions) {
  const out = [];
  for (const name of readdirSync(path.join(ROOT, dir))) {
    const relative = path.posix.join(dir, name);
    const full = path.join(ROOT, relative);
    if (statSync(full).isDirectory()) {
      if (["dist", "vendor"].includes(name)) continue;
      out.push(...files(relative, extensions));
    } else if (extensions.some(ext => name.endsWith(ext))) {
      out.push(relative);
    }
  }
  return out;
}

const isAdmin = (file) => /(^|\/)admin[^/]*$/.test(file);

describe("no browser windows and no glass (E1, G1)", () => {
  const sources = [...files("static", [".js"]), ...files("templates", [".html"])].filter(file => !isAdmin(file));

  it("never calls alert() or confirm() outside the admin", () => {
    const offenders = [];
    for (const file of sources) {
      read(file).split("\n").forEach((line, index) => {
        const code = line.trim();
        if (code.startsWith("//") || code.startsWith("*") || code.startsWith("/*")) return;
        if (/(?<![\w.$-])(?:window\.)?(?:alert|confirm)\s*\(/.test(code) && !/function\s+confirm\s*\(/.test(code)) {
          offenders.push(`${file}:${index + 1}: ${code}`);
        }
      });
    }
    expect(offenders).toEqual([]);
  });

  it("draws no backdrop blur anywhere in the app or on the public pages", () => {
    const offenders = [];
    for (const file of files("static", [".css"]).filter(file => !isAdmin(file))) {
      read(file).split("\n").forEach((line, index) => {
        const match = /(?:-webkit-)?backdrop-filter\s*:\s*([^;]+)/.exec(line);
        if (match && match[1].trim() !== "none") offenders.push(`${file}:${index + 1}: ${line.trim()}`);
      });
    }
    for (const file of sources) {
      if (/backdropFilter\s*=|["']backdrop-filter["']\s*,/.test(read(file))) offenders.push(file);
    }
    expect(offenders).toEqual([]);
  });

  it("keeps one scrim token behind every modal layer", () => {
    const overlays = read("static/css/overlays.css");
    for (const layer of ["dialog.modal", ".memory-edit-backdrop", ".agent-google-overlay", ".claim-sheet-backdrop"]) {
      expect(overlays).toMatch(new RegExp(`${layer.replace(/\./g, "\\.")}[^{]*\\{[^}]*background: var\\(--scrim\\)`));
    }
    expect(overlays).toContain(".answer-reader-dialog::backdrop {\n  background: var(--scrim");
    expect(read("static/css/shell.css")).toMatch(/body::after \{[^}]*background: var\(--scrim\)/);
    // The landing page's sentence card dims with the same token (it has no
    // overlays.css of its own); it used to carry a raw, darker rgba.
    expect(read("static/css/landing.css")).toMatch(/\.claim-sheet-backdrop \{[^}]*background: var\(--scrim\);/);
    // So does the Agent activity sheet; an --ink tint turned pale in dark mode.
    expect(read("static/css/agent-chat.css")).toMatch(/\.agent-sidebar-scrim \{[^}]*background: var\(--scrim\);/);
    const foundation = read("static/css/foundation.css");
    expect(foundation).toMatch(/:root \{[\s\S]*--scrim: rgba/);
    expect(foundation).toMatch(/\.dark-mode \{\s*--scrim: rgba/);
  });
});

describe("one dialog material and motion (C1, G1)", () => {
  const template = read("templates/index.html");

  it("makes every modal window a native <dialog class=\"modal\">", () => {
    expect(template).not.toMatch(/<div[^>]+class="modal[ "]/);
    expect(template).not.toMatch(/role="dialog"[^>]*aria-modal="true"/);
    for (const id of ["loginModal", "feedbackModal", "shareModal", "attachmentViewerModal", "proFeatureModal", "systemPromptModal", "helpModal"]) {
      expect(template).toMatch(new RegExp(`<dialog id="${id}" class="modal`));
    }
  });

  it("fades and rises in and goes back out, with the one surface", () => {
    const overlays = read("static/css/overlays.css");
    expect(overlays).toContain("display var(--dur-state) allow-discrete");
    expect(overlays).toContain("overlay var(--dur-state) allow-discrete");
    expect(overlays).toMatch(/@starting-style \{\s*dialog\.modal\[open\] \{ opacity: 0; \}\s*dialog\.modal\[open\] > \.modal-content \{ translate: 0 8px; scale: 0\.98; \}/);
    expect(overlays).toMatch(/dialog\.modal > \.modal-content \{\s*translate: 0 8px;\s*scale: 0\.98;\s*transition:\s*translate var\(--dur-state\) var\(--ease-in\)/);
    expect(overlays).toMatch(/> :is\(\.modal-content[^)]*\) \{[^}]*border-radius: var\(--radius-lg\);\s*background: var\(--raise\);\s*box-shadow: var\(--lift\);/);
  });
});

describe("App.modalDialog", () => {
  const contexts = [];
  afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

  function boot(body) {
    const ctx = loadScripts(["static/js/motion.js", "static/js/modal-dialog.js", "static/js/popover.js"], {
      body,
      // jsdom lays nothing out; every control here is on screen.
      before(window) { window.HTMLElement.prototype.getClientRects = () => [{ width: 10, height: 10 }]; },
    });
    contexts.push(ctx);
    return ctx;
  }

  it("keeps Tab inside, closes on Escape and gives focus back (E6)", () => {
    const { window, document } = boot(`
      <button id="opener">Open</button>
      <dialog id="d" class="modal"><button id="first">One</button><a id="mid" href="#x">Two</a><button id="last">Three</button></dialog>`);
    const dialog = document.getElementById("d");
    document.getElementById("opener").focus();
    window.App.modalDialog.open(dialog, { focus: document.getElementById("first") });
    expect(document.activeElement.id).toBe("first");
    const tab = (shiftKey) => {
      const event = new window.KeyboardEvent("keydown", { key: "Tab", shiftKey, bubbles: true, cancelable: true });
      document.activeElement.dispatchEvent(event);
      return event.defaultPrevented;
    };
    expect(tab(true)).toBe(true);
    expect(document.activeElement.id).toBe("last");
    expect(tab(false)).toBe(true);
    expect(document.activeElement.id).toBe("first");
    document.activeElement.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    expect(dialog.open).toBe(false);
    expect(document.activeElement.id).toBe("opener");
  });

  it("closes an open popover when a dialog opens", () => {
    const { window, document } = boot(`<div id="menu"></div><dialog id="d" class="modal"><button>x</button></dialog>`);
    const close = vi.fn();
    const menu = document.getElementById("menu");
    window.App.popover.register(menu, { close });
    window.App.popover.opened(menu);
    window.App.modalDialog.open(document.getElementById("d"));
    expect(close).toHaveBeenCalledOnce();
    expect(window.App.popover.isOpen(menu)).toBe(false);
  });

  // Review F (2026-10-21): a dialog chosen in a menu ("Shared links", "Log
  // out") gave focus back to nothing, as its menu item was gone by then.
  it("gives focus back to the menu's control after a dialog chosen in that menu", () => {
    const { window, document } = boot(`
      <button id="avatar">A</button>
      <div id="menu" hidden><button id="item" role="menuitem">Shared links</button></div>
      <dialog id="d" class="modal"><button id="inside">x</button></dialog>`);
    const menu = document.getElementById("menu");
    const avatar = document.getElementById("avatar");
    const close = () => { menu.hidden = true; window.App.popover.closed(menu); };
    window.App.popover.register(menu, { close });
    // The item opens the dialog while its menu is still open ...
    menu.hidden = false;
    window.App.popover.opened(menu, { trigger: avatar });
    document.getElementById("item").focus();
    window.App.modalDialog.open(document.getElementById("d"));
    window.App.modalDialog.close(document.getElementById("d"));
    expect(document.activeElement).toBe(avatar);
    // ... or closes the menu first, and focus has fallen to <body>.
    menu.hidden = false;
    window.App.popover.opened(menu, { trigger: avatar });
    document.getElementById("item").focus();
    close();
    document.activeElement.blur();
    expect(document.activeElement).toBe(document.body);
    window.App.modalDialog.open(document.getElementById("d"));
    window.App.modalDialog.close(document.getElementById("d"));
    expect(document.activeElement).toBe(avatar);
  });

  it("hands out the one drawn close cross (G3)", () => {
    const { window } = boot("");
    expect(window.App.closeIcon()).toContain('class="close-icon"');
    expect(window.App.closeIcon()).toContain('viewBox="0 0 16 16"');
  });
});

describe("App.popover (C4, E6, E10)", () => {
  const contexts = [];
  afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

  function boot(body) {
    const ctx = loadScripts(["static/js/motion.js", "static/js/popover.js"], { body });
    contexts.push(ctx);
    return ctx;
  }

  it("keeps exactly one open, even when the opener stopped its click", () => {
    const { window, document } = boot(`<div id="account"></div><div id="quota"></div>`);
    const account = document.getElementById("account");
    const quota = document.getElementById("quota");
    const closeAccount = vi.fn(() => window.App.popover.closed(account));
    window.App.popover.register(account, { close: closeAccount });
    window.App.popover.register(quota, { close: () => {} });
    window.App.popover.opened(account);
    window.App.popover.opened(quota);
    expect(closeAccount).toHaveBeenCalledOnce();
    expect(window.App.popover.isOpen(quota)).toBe(true);
    expect(window.App.popover.isOpen(account)).toBe(false);
  });

  it("aims the way in from the control that opened it", () => {
    const { window, document } = boot(`<button id="low">+</button><div id="menu"></div>`);
    const trigger = document.getElementById("low");
    window.innerHeight = 800;
    trigger.getBoundingClientRect = () => ({ top: 700, height: 32, width: 32, left: 10 });
    const menu = document.getElementById("menu");
    window.App.popover.opened(menu, { trigger });
    expect(menu.style.getPropertyValue("--popover-shift")).toBe("4px");
    expect(menu.style.getPropertyValue("--popover-origin-y")).toBe("100%");
    trigger.getBoundingClientRect = () => ({ top: 40, height: 32, width: 32, left: 10 });
    window.App.popover.opened(menu, { trigger });
    expect(menu.style.getPropertyValue("--popover-shift")).toBe("-4px");
  });

  it("moves through a menu like the account menu and gives focus back on Escape", () => {
    const { window, document } = boot(`
      <button id="opener">+</button>
      <div id="menu"><button>One</button><button>Two</button><button>Three</button></div>`);
    const menu = document.getElementById("menu");
    const items = () => Array.from(menu.querySelectorAll("button"));
    const close = vi.fn();
    window.App.popover.menuKeys(menu, { items, close, opener: document.getElementById("opener") });
    items()[0].focus();
    const key = (name) => document.activeElement.dispatchEvent(new window.KeyboardEvent("keydown", { key: name, bubbles: true, cancelable: true }));
    key("ArrowDown");
    expect(document.activeElement.textContent).toBe("Two");
    key("End");
    expect(document.activeElement.textContent).toBe("Three");
    key("ArrowDown");
    expect(document.activeElement.textContent).toBe("One");
    key("ArrowUp");
    expect(document.activeElement.textContent).toBe("Three");
    key("Home");
    expect(document.activeElement.textContent).toBe("One");
    key("Escape");
    expect(close).toHaveBeenCalledWith(expect.objectContaining({ reason: "escape" }));
    expect(document.activeElement.id).toBe("opener");
  });

  it("gives every popover a way in and a way out in CSS", () => {
    const overlays = read("static/css/overlays.css");
    for (const popover of [".attach-menu", ".email-popup", ".model-picker-menu", ".sidebar-quota",
      ".consensus-actions-menu", ".claim-popover", ".bookmark-menu", ".agent-files-menu"]) {
      expect(overlays).toContain(popover);
    }
    expect(overlays).toContain("transition-behavior: allow-discrete;");
    expect(overlays).toMatch(/\[data-popover\]\.is-leaving\) \{\s*opacity: 0;\s*translate: 0 var\(--popover-shift, -4px\);\s*scale: 0\.98;/);
  });
});

describe("one close cross (G3)", () => {
  it("uses no font glyph for closing anything in the app", () => {
    const offenders = [];
    for (const file of [...files("static/js", [".js"]), "templates/index.html", "static/firebase.js"]) {
      if (isAdmin(file)) continue;
      read(file).split("\n").forEach((line, index) => {
        if (/&times;|&#10005;|&#215;|[×✕]/.test(line) && /close|dismiss|remove|exclude/i.test(line)) {
          offenders.push(`${file}:${index + 1}: ${line.trim()}`);
        }
      });
    }
    expect(offenders).toEqual([]);
  });

  it("draws it once, in foundation.css", () => {
    const foundation = read("static/css/foundation.css");
    expect(foundation).toMatch(/\.close-button \{[^}]*width: 32px;\s*height: 32px;/);
    expect(foundation).toMatch(/\.close-icon \{[^}]*width: 16px;\s*height: 16px;[^}]*stroke-width: 1\.75;/);
    expect(foundation).toMatch(/@media \(pointer: coarse\) \{\s*\.close-button::after \{[^}]*inset: -6px;/);
  });
});

describe("one tooltip (E12)", () => {
  const contexts = [];
  afterEach(() => { vi.useRealTimers(); contexts.splice(0).forEach(ctx => ctx.window.close()); });

  function pointer(window, type, target, pointerType = "mouse", relatedTarget = null) {
    const event = new window.Event(type, { bubbles: true });
    Object.defineProperty(event, "pointerType", { value: pointerType });
    Object.defineProperty(event, "relatedTarget", { value: relatedTarget });
    target.dispatchEvent(event);
  }

  it("takes over a title for the pointer and gives it back, and shows a mark's on a tap", () => {
    vi.useFakeTimers();
    const ctx = loadScripts(["static/js/tooltip.js"], {
      body: `<button id="send" title="Send question" aria-label="Send question"></button>
        <span id="mark" role="img" title="OpenAI · GPT-6 Luna"></span>
        <button id="same" title="Settings">Settings</button>`,
    });
    contexts.push(ctx);
    const { window, document } = ctx;
    window.App.tooltip.init();
    const tip = document.querySelector(".global-tooltip");
    expect(tip.getAttribute("role")).toBe("tooltip");
    const send = document.getElementById("send");
    pointer(window, "pointerover", send);
    // The browser's own grey tooltip has nothing to show while ours waits.
    expect(send.hasAttribute("title")).toBe(false);
    vi.advanceTimersByTime(499);
    expect(tip.classList.contains("visible")).toBe(false);
    vi.advanceTimersByTime(10);
    expect(tip.classList.contains("visible")).toBe(true);
    expect(tip.textContent).toBe("Send question");
    expect(send.getAttribute("aria-describedby")).toBe(tip.id);
    pointer(window, "pointerout", send);
    expect(tip.classList.contains("visible")).toBe(false);
    expect(send.getAttribute("title")).toBe("Send question");

    // A tooltip that only repeats the visible label is not shown.
    pointer(window, "pointerover", document.getElementById("same"));
    vi.advanceTimersByTime(600);
    expect(tip.classList.contains("visible")).toBe(false);
    pointer(window, "pointerout", document.getElementById("same"));

    // Under a finger: a tap on a mark that does nothing else explains it.
    pointer(window, "pointerup", document.getElementById("mark"), "touch");
    expect(tip.classList.contains("visible")).toBe(true);
    expect(tip.textContent).toBe("OpenAI · GPT-6 Luna");
    vi.advanceTimersByTime(3000);
    expect(tip.classList.contains("visible")).toBe(false);
  });
});

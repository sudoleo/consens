// static/js/i18n.js: what scripts write on a German page arrives in German,
// with the rules of app/core/i18n.py (runs, markers, patterns, skips).
import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const ENTRIES = {
  "New chat": "Neuer Chat",
  "Copy": "Kopieren",
  "Settings": "Einstellungen",
  "Read the <0>privacy policy</0> first.": "Lies zuerst die <0>Datenschutzerklärung</0>.",
  "{n} chats": "{n} Chats",
  "Switch to {mode}": "Zu {mode} wechseln",
  "Compare": "Vergleich",
  "Plan": "Tarif",
  "Schedule": "Plan",
  "Working…": "Arbeitet …",
  "Table: {headings}": "Tabelle: {headings}",
};

function germanPage(body = "") {
  return loadScripts(["static/js/i18n.js", "static/js/app-text.js"], {
    body,
    base: false,
    before(window) {
      window.__consensI18n = { lang: "de", entries: ENTRIES };
    },
  });
}

async function settle(window) {
  await Promise.resolve();
  window.App.i18n.flush();
}

describe("i18n.js on a German page", () => {
  it("translates what a script writes, text and attributes", async () => {
    const { window, document } = germanPage("<main></main>");
    const button = document.createElement("button");
    button.textContent = "New chat";
    button.title = "Settings";
    document.querySelector("main").append(button);
    await settle(window);
    expect(button.textContent).toBe("Neuer Chat");
    expect(button.title).toBe("Einstellungen");
  });

  it("looks a sentence up whole and moves its link, listeners included", async () => {
    const { window, document } = germanPage("<main></main>");
    const p = document.createElement("p");
    const link = document.createElement("a");
    let clicks = 0;
    link.addEventListener("click", () => { clicks += 1; });
    link.textContent = "privacy policy";
    p.append("Read the ", link, " first.");
    document.querySelector("main").append(p);
    await settle(window);
    expect(p.innerHTML).toBe("Lies zuerst die <a>Datenschutzerklärung</a>.");
    p.querySelector("a").click();
    expect(clicks).toBe(1);
    expect(p.querySelector("a")).toBe(link);
  });

  it("fills patterns and translates a captured word that has an entry", async () => {
    const { window, document } = germanPage("<main><span id=a></span><span id=b></span></main>");
    document.getElementById("a").textContent = "3 chats";
    document.getElementById("b").textContent = "Switch to Compare";
    await settle(window);
    expect(document.getElementById("a").textContent).toBe("3 Chats");
    expect(document.getElementById("b").textContent).toBe("Zu Vergleich wechseln");
  });

  it("never translates its own German twice", async () => {
    const { window, document } = germanPage("<main><p id=p></p></main>");
    const p = document.getElementById("p");
    p.textContent = "Schedule";
    await settle(window);
    expect(p.textContent).toBe("Plan");
    p.append(document.createElement("span"));
    await settle(window);
    expect(p.textContent).toBe("Plan");
  });

  it("leaves content, code and editable text alone", async () => {
    const { window, document } = germanPage(
      '<main><div id=answer data-i18n-skip></div><code id=code></code><div id=edit contenteditable="true"></div><div class="bookmark"><p id=title></p></div></main>'
    );
    for (const id of ["answer", "code", "edit", "title"]) document.getElementById(id).textContent = "New chat";
    await settle(window);
    for (const id of ["answer", "code", "edit", "title"]) expect(document.getElementById(id).textContent).toBe("New chat");
  });

  it("follows a script that keeps changing the same label", async () => {
    const { window, document } = germanPage("<main><span id=s></span></main>");
    const span = document.getElementById("s");
    span.textContent = "Copy";
    await settle(window);
    expect(span.textContent).toBe("Kopieren");
    // The set-if-changed idiom compares with what the page shows.
    if (span.textContent !== window.App.t("Copy")) span.textContent = "Copy";
    expect(span.textContent).toBe("Kopieren");
    span.textContent = "Settings";
    await settle(window);
    expect(span.textContent).toBe("Einstellungen");
  });

  it("translates a field's placeholder, options and context words, never what was typed", async () => {
    const { window, document } = germanPage('<main><textarea id=t></textarea><select id=s data-i18n-context="agent freedom"></select></main>');
    window.__consensI18n.entries["agent freedom|Plan"] = "Frei";
    const field = document.getElementById("t");
    field.placeholder = "Settings";
    field.value = "New chat";
    const option = document.createElement("option");
    option.textContent = "Copy";
    document.getElementById("s").append(option);
    await settle(window);
    expect(field.placeholder).toBe("Einstellungen");
    expect(field.value).toBe("New chat");
    expect(option.textContent).toBe("Kopieren");
    expect(window.App.t("Plan", null, "no such context")).toBe("Tarif");
  });

  it("translates a value a pattern caught when it has an entry of its own", async () => {
    const { window, document } = germanPage("<main><p id=p></p></main>");
    document.getElementById("p").textContent = "Switch to Compare";
    await settle(window);
    expect(document.getElementById("p").textContent).toBe("Zu Vergleich wechseln");
  });

  it("gives App.t and German formats to the app", () => {
    const { window } = germanPage();
    expect(window.App.lang).toBe("de");
    expect(window.App.t("Copy")).toBe("Kopieren");
    expect(window.App.t("{n} chats", { n: 2 })).toBe("2 Chats");
    expect(window.App.t("Table: {headings}", { headings: "A, B" })).toBe("Tabelle: A, B");
    expect(window.App.t("Not in the dictionary")).toBe("Not in the dictionary");
    expect(window.App.format.LOCALE).toBe("de-DE");
    expect(window.App.format.number(48213)).toBe("48.213");
    expect(window.App.format.relative(Date.now() - 12 * 60 * 1000)).toBe("vor 12 Min.");
    expect(window.App.format.duration(187000)).toBe("3 Min. 7 Sek.");
  });
});

describe("i18n.js on an English page", () => {
  it("changes nothing and App.t only fills placeholders", async () => {
    const { window, document } = loadScripts([], { body: "<main></main>" });
    expect(window.App.lang).toBe("en");
    expect(window.App.t("{n} chats", { n: 2 })).toBe("2 chats");
    expect(window.App.format.LOCALE).toBe("en-US");
    expect(window.App.format.relative(Date.now() - 12 * 60 * 1000)).toBe("12m ago");
    const button = document.createElement("button");
    button.textContent = "New chat";
    document.querySelector("main").append(button);
    await Promise.resolve();
    expect(button.textContent).toBe("New chat");
  });
});

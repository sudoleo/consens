import { afterEach, describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// /app#q=<text> (app-bootstrap.js): the one way a question comes in from
// outside. It fills the field in the first frame and never sends; the
// fragment leaves the address before anything else can read it.
const BODY = `
  <meta id="appBootstrapConfig" data-firebase-api-key="test-key" data-model-families="[]"
    data-max-run-families="6" data-consensus-presets="[]" data-default-consensus-preset="&quot;fast&quot;">
  <div class="input-section">
    <div class="chat-input-container">
      <textarea id="questionInput" placeholder="Enter your question"></textarea>
      <div class="input-actions-container"><button id="sendButton" aria-disabled="true" disabled></button></div>
    </div>
    <div id="composerStarters"></div>
    <footer class="app-footer"></footer>
  </div>`;
const DRAFT_KEY = "consensio.questionDraft.v1";
const token = uid => `x.${Buffer.from(JSON.stringify({ user_id: uid })).toString("base64url")}.y`;

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function open(address, { storage = {}, scripts = [], vendor = "Google Inc.", installed = false } = {}) {
  const ctx = loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/composer-autosize.js",
    "static/js/app-bootstrap.js", ...scripts], {
    body: BODY,
    before(window) {
      window.history.replaceState(null, "", address);
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      window.matchMedia = query => ({ matches: installed && query.includes("display-mode: standalone"),
        addEventListener() {}, removeEventListener() {} });
      Object.defineProperty(window.navigator, "vendor", { configurable: true, get: () => vendor });
      window.umami = { track: (name, data) => (window.__tracked ||= []).push([name, data]) };
    },
  });
  contexts.push(ctx);
  // The deferred bundle runs after parsing; jsdom is still "loading" here.
  if (scripts.length) {
    ctx.document.dispatchEvent(new ctx.window.Event("DOMContentLoaded"));
    ctx.window.dispatchEvent(new ctx.window.Event("load"));
  }
  return ctx;
}
const field = document => document.getElementById("questionInput");
const APP = ["static/js/app-core.js", "static/js/composer-invite.js"];

describe("a question brought by the address", () => {
  it("fills the field, never sends, and leaves the address at once", () => {
    const { window, document } = open("/app?chat=&utm_source=shortcut#q=Is+a+heat+pump+worth+it%3F");
    expect(field(document).value).toBe("Is a heat pump worth it?");
    expect(window.location.href).toBe("https://consens.io/app?chat=&utm_source=shortcut");
    expect(window.App.questionLink).toMatchObject({ opened: true, filled: true });
    // A guest's Send asks for the sign-in; nothing went out by itself.
    expect(document.getElementById("sendButton").disabled).toBe(false);
  });

  it("reads the search keyword's form (#?q=) and both ways of writing a space", () => {
    const parse = open("/app").window.App.questionLink.parse;
    expect(parse("#?q=C%2B%2B+vs+Rust")).toBe("C++ vs Rust");
    expect(parse("#q=Tom%20%26%20Jerry")).toBe("Tom & Jerry");
    expect(parse("#q=")).toBe("");
    expect(parse("#settings")).toBeNull();
    expect(parse("")).toBeNull();
  });

  it("sets only text, cut to its limit, without control or direction marks", () => {
    const parse = open("/app").window.App.questionLink.parse;
    expect(parse("#q=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E")).toBe("<img src=x onerror=alert(1)>");
    expect(parse("#q=a%E2%80%AEb%00c%0D%0Ad%09e")).toBe("abc\nd\te");
    const long = parse(`#q=${"x".repeat(2100)}`);
    expect(long).toHaveLength(2000);
    // Cut by characters, never inside one.
    expect(Array.from(parse(`#q=${encodeURIComponent("😀".repeat(2100))}`))).toHaveLength(2000);
    const { document } = open("/app#q=%3Cb%3Ebold%3C%2Fb%3E");
    expect(field(document).value).toBe("<b>bold</b>");
    expect(document.querySelector("b")).toBeNull();
  });

  it("never replaces a draft that waits in the field", () => {
    const draft = JSON.stringify({ text: "My own question", at: Date.now() });
    const { window, document } = open("/app#q=Someone+else%27s", { storage: { [DRAFT_KEY]: draft } });
    expect(field(document).value).toBe("My own question");
    expect(window.App.questionLink).toMatchObject({ opened: true, filled: false });
    expect(window.location.hash).toBe("");
  });

  it("keeps a guest's question as a draft through the sign-in, but not an account's", () => {
    const guest = open("/app#q=Guest+question").window;
    const kept = guest.localStorage.getItem(DRAFT_KEY);
    expect(JSON.parse(kept)).toMatchObject({ text: "Guest question", link: true });
    const account = open("/app#q=Account+question", { storage: { id_token: token("u1") } });
    expect(field(account.document).value).toBe("Account question");
    expect(account.window.localStorage.getItem(DRAFT_KEY)).toBeNull();
    // Only for the page the link opened: a reload starts empty.
    const reload = open("/app", { storage: { [DRAFT_KEY]: kept } });
    expect(field(reload.document).value).toBe("");
    expect(reload.window.localStorage.getItem(DRAFT_KEY)).toBeNull();
  });

  it("counts the way in once the page has loaded, and the question it brought as the source of the ask", () => {
    const { window } = open("/app#q=From+a+link", { scripts: APP });
    expect(window.__tracked).toEqual([["app_question_link", { filled: true, guest: false }]]);
    expect(window.App.composerInvite.takeAskContext()).toEqual({ source: "link" });
    expect(window.App.composerInvite.takeAskContext()).toEqual({ source: "typed" });
  });

  it("reads nothing outside /app", () => {
    const { window, document } = open("/app/watches#q=Hello");
    expect(field(document).value).toBe("");
    expect(window.location.hash).toBe("#q=Hello");
    expect(window.App.questionLink.opened).toBe(false);
  });

  it("takes a question that arrives while the app is open, into an empty field only", () => {
    const { window, document } = open("/app", { scripts: APP });
    window.App.isGuestComposer = () => true;
    document.body.classList.add("is-hero");
    window.location.hash = "#q=Second+question";
    window.dispatchEvent(new window.HashChangeEvent("hashchange"));
    expect(field(document).value).toBe("Second question");
    expect(window.location.hash).toBe("");
    expect(document.activeElement).toBe(field(document));
    expect(field(document).selectionStart).toBe("Second question".length);
    window.location.hash = "#q=Third";
    window.dispatchEvent(new window.HashChangeEvent("hashchange"));
    expect(field(document).value).toBe("Second question");
    expect(window.__tracked.map(([name, data]) => [name, data.filled])).toEqual([
      ["app_question_link", true], ["app_question_link", false]]);
    // The source of the "ask" is the link; never its words.
    expect(window.App.composerInvite.takeAskContext()).toEqual({ source: "link" });
  });
});

describe("the bar of an installed app's window", () => {
  it("follows the page's theme in Chrome's or Edge's window, never in a tab or in Safari", () => {
    const tab = open("/app").document;
    expect(tab.querySelector('meta[name="theme-color"]')).toBeNull();
    const safari = open("/app", { installed: true, vendor: "Apple Computer, Inc." }).document;
    expect(safari.querySelector('meta[name="theme-color"]')).toBeNull();
    const { window, document } = open("/app", { installed: true });
    document.body.style.setProperty("--ground", "#050505");
    window.App.windowColour();
    expect(document.querySelector('meta[name="theme-color"]').content).toBe("#050505");
  });
});

import { afterEach, describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The first frame of /app is the composer the app settles on (Apple-Audit
// B1, B2, B4, B6, B11, B13): app-bootstrap.js draws it from what this
// browser stored, before any deferred module runs.
const FAMILIES = [
  { provider: "openai", label: "OpenAI", title: "OpenAI", checkboxId: "openaiCheck", icon: "/static/openai.svg", iconClass: "chatgpt-logo" },
  { provider: "gemini", label: "Gemini", title: "Gemini", checkboxId: "geminiCheck", icon: "/static/gemini.svg", iconClass: "" },
  { provider: "grok", label: "Grok", title: "Grok", checkboxId: "grokCheck", icon: "/static/grok.svg", iconClass: "grok-logo" },
];
const attr = value => JSON.stringify(value).replace(/"/g, "&quot;");
const BODY = `
  <meta id="appBootstrapConfig" data-firebase-api-key="test-key" data-model-families="${attr(FAMILIES)}"
    data-max-run-families="6" data-agent-default-label="Claude Sonnet 5.5"
    data-consensus-presets="${attr([{ id: "fast", label: "Daily" }])}" data-default-consensus-preset="${attr("fast")}">
  <div id="authTopActions" hidden></div>
  <div id="appSidebar" class="sidebar">
    <div id="modelSelectionArea" hidden>
      <input type="checkbox" id="openaiCheck" checked><input type="checkbox" id="geminiCheck" checked><input type="checkbox" id="grokCheck" checked>
    </div>
    <div id="bookmarksContainer"></div><div id="loginContainer" hidden></div>
  </div>
  <div class="input-section">
    <p class="hero-greeting">What should the models cross-check?</p>
    <div class="chat-input-container">
      <textarea id="questionInput" placeholder="Enter your question"></textarea>
      <div class="composer-models">
        <div id="agentModelControls" class="agent-model-controls" hidden>
          <div class="select-wrapper agent-model-picker"><select id="agentModelDropdown" aria-label="Chat model"><option value="">Loading models…</option></select></div>
          <div class="select-wrapper agent-effort-control"><select id="agentReasoningEffort"><option value="default">Auto</option></select></div>
          <button id="agentModelsRetry" hidden>Reload models</button>
        </div>
        <div class="consensus-model"><div class="select-wrapper"><select id="consensusModelDropdown" aria-label="Models and consensus engine"><option>Gemini 3.5 Flash · Pro</option></select></div></div>
      </div>
      <div class="input-actions-container">
        <button type="button" class="demo-chip demo-action" hidden>Try the demo</button>
        <button id="sendButton" aria-disabled="true" disabled></button>
      </div>
    </div>
    <div id="composerModeBar"><span id="composerReasoningState">Off</span><span id="composerModelIcons"></span></div>
    <div id="composerStarters"><button class="composer-starter" data-starter="check">Check an AI answer</button></div>
  </div>`;

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function paint({ storage = {}, session = {}, sizes = [] } = {}) {
  const ctx = loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/composer-starters.js",
    "static/js/composer-autosize.js", "static/js/app-bootstrap.js"], {
    body: BODY,
    before(window) {
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      Object.entries(session).forEach(([key, value]) => window.sessionStorage.setItem(key, value));
      window.matchMedia = () => ({ matches: false });
      // The autosizer's twin answers with the draft's height.
      Object.defineProperty(window.HTMLTextAreaElement.prototype, "scrollHeight", {
        configurable: true, get() { return this.classList.contains("input-field-twin") ? (sizes.shift() ?? 96) : 0; } });
    },
  });
  contexts.push(ctx);
  return ctx;
}
const token = uid => `x.${Buffer.from(JSON.stringify({ user_id: uid })).toString("base64url")}.y`;
const chip = document => document.querySelector("#agentModelControls .model-picker-display");

describe("the session a first frame expects (B4)", () => {
  it("paints a guest without any stored session, in Agent's composer of a new chat (H3)", () => {
    const { window, document } = paint();
    expect(window.App.expectedSession()).toMatchObject({ known: false, account: false });
    expect(window.App.isGuest()).toBe(true);
    expect(document.body.classList.contains("is-guest")).toBe(true);
    expect(document.getElementById("authTopActions").hidden).toBe(false);
    // What an account sees by default (Max, Apple-Audit H3): Agent's chip
    // with the default model and the comparison count, its greeting and
    // Reasoning; no Consensus chip, no account placeholders.
    expect(document.documentElement.classList.contains("agent-shell-expected")).toBe(true);
    expect(document.body.classList.contains("single-agent-active")).toBe(true);
    expect(document.querySelector(".hero-greeting").textContent).toBe("What can I help you with?");
    expect(document.getElementById("agentModelControls").hidden).toBe(false);
    expect(chip(document).querySelector(".model-picker-display-text").textContent).toBe("Claude Sonnet 5.5");
    expect(chip(document).querySelector(".model-picker-display-count").textContent).toBe("+3");
    expect(document.querySelector(".consensus-model").hidden).toBe(true);
    expect(document.getElementById("composerReasoningState").textContent).toBe("Auto");
    expect(document.getElementById("questionInput").placeholder).toBe("Ask anything, or paste an AI answer to check it");
    expect(document.querySelector(".demo-chip").hidden).toBe(false);
    expect(document.querySelectorAll("#bookmarksContainer .skeleton-bookmark")).toHaveLength(0);
  });

  it("keeps a guest's own choice of Consensus, and gives no Agent while the login cannot load", () => {
    const chose = paint({ storage: { runMode: "consensus" } }).document;
    expect(chose.documentElement.classList.contains("agent-shell-expected")).toBe(false);
    expect(chose.body.classList.contains("single-agent-active")).toBe(false);
    expect(chose.querySelector(".hero-greeting").textContent).toBe("What should the models cross-check?");
    const { window, document } = paint();
    document.documentElement.dataset.authUnavailable = "true";
    expect(window.App.isGuest()).toBe(false);
    expect(window.App.expectsAgent()).toBe(false);
    window.dispatchEvent(new window.CustomEvent("consensio:auth-unavailable"));
    expect(document.documentElement.classList.contains("agent-shell-expected")).toBe(false);
    // An unconfirmed sign-in is an account, not a guest.
    window.auth = { currentUser: { uid: "u1", emailVerified: false } };
    delete document.documentElement.dataset.authUnavailable;
    expect(window.App.isGuest()).toBe(false);
  });

  it.each([
    ["our ID token", { storage: { id_token: token("u1") } }],
    ["the user Firebase keeps (no ID token yet: a sign-in by Google pop-up)",
      { storage: { "firebase:authUser:test-key:[DEFAULT]": JSON.stringify({ uid: "u1", emailVerified: true }) } }],
    ["a Google sign-in coming back from the redirect", { session: { "consensio.googleRedirectPending": "1" } }],
  ])("paints the account and Agent from %s", (_, stored) => {
    const { window, document } = paint(stored);
    expect(window.App.expectedSession().account).toBe(true);
    expect(document.body.classList.contains("is-guest")).toBe(false);
    expect(document.getElementById("authTopActions").hidden).toBe(true);
    expect(document.documentElement.classList.contains("agent-shell-expected")).toBe(true);
    expect(document.body.classList.contains("single-agent-active")).toBe(true);
    expect(document.querySelector(".hero-greeting").textContent).toBe("What can I help you with?");
    // The account's placeholders are there from the first frame (B11).
    expect(document.querySelectorAll("#bookmarksContainer .skeleton-bookmark")).toHaveLength(4);
    expect(document.getElementById("loginContainer").hidden).toBe(false);
  });

  it("keeps Consensus for an account this browser saw without Agent, and for an unconfirmed address", () => {
    const denied = paint({ storage: { id_token: token("u1"), agentShellExpected: "0" } }).document;
    expect(denied.documentElement.classList.contains("agent-shell-expected")).toBe(false);
    expect(denied.querySelector(".consensus-model").hidden).toBe(false);
    expect(denied.querySelector(".consensus-model .model-picker-display").textContent).toBe("3 models · Daily");
    const unverified = paint({ storage: { "firebase:authUser:test-key:[DEFAULT]": JSON.stringify({ uid: "u1", emailVerified: false }) } }).document;
    expect(unverified.body.classList.contains("is-guest")).toBe(false);
    expect(unverified.documentElement.classList.contains("agent-shell-expected")).toBe(false);
  });
});

describe("the composer's first frame (B1, B2, B13)", () => {
  it("draws Agent's chip with the remembered words, the count and Reasoning, and no Consensus chip", () => {
    const look = JSON.stringify({ uid: "u1", agentModel: "Claude Opus 5.5", agentEffort: "High" });
    const { document } = paint({ storage: { id_token: token("u1"), "consensio.firstFrame.v1": look,
      pref_check_Grok: "false" } });
    expect(document.getElementById("agentModelControls").hidden).toBe(false);
    expect(document.querySelector(".agent-effort-control").hidden).toBe(true);
    expect(chip(document).dataset.seeded).toBe("true");
    expect(chip(document).querySelector(".model-picker-display-text").textContent).toBe("Claude Opus 5.5");
    expect(document.getElementById("agentModelDropdown").classList.contains("native-model-picker")).toBe(true);
    expect(document.querySelector(".consensus-model").hidden).toBe(true);
    expect(document.getElementById("composerReasoningState").textContent).toBe("High");
    // Grok left the comparison (the account's stored choice): two marks, "+2".
    expect(document.getElementById("grokCheck").checked).toBe(false);
    expect(chip(document).querySelector(".model-picker-display-count").textContent).toBe("+2");
    const marks = [...document.querySelectorAll("#composerModelIcons .composer-model-icon")];
    expect(marks.map(mark => mark.dataset.provider)).toEqual(["openai", "gemini"]);
    expect(marks[0].querySelector("img").getAttribute("src")).toBe("/static/openai.svg");
    expect(marks[0].querySelector("img").classList.contains("chatgpt-logo")).toBe(true);
  });

  it("names the default model without a remembered look, and never another account's words", () => {
    const other = JSON.stringify({ uid: "someone-else", agentModel: "Claude Opus 5.5", agentEffort: "High" });
    const { document } = paint({ storage: { id_token: token("u1"), "consensio.firstFrame.v1": other } });
    expect(chip(document).querySelector(".model-picker-display-text").textContent).toBe("Claude Sonnet 5.5");
    expect(document.getElementById("composerReasoningState").textContent).toBe("Auto");
  });

  it("offers the demo to a guest once, decided before the first paint", () => {
    const fresh = paint().document;
    expect(fresh.querySelector(".demo-chip").hidden).toBe(false);
    const used = paint({ storage: { demoChipDismissed: "1" } }).document;
    expect(used.querySelector(".demo-chip")).toBeNull();
    // Send waits for a question in both.
    expect(fresh.getElementById("sendButton").disabled).toBe(true);
  });

  it("puts a guest's waiting question in the field, sized, with Send ready (B6)", () => {
    const draft = JSON.stringify({ text: "Is a heat pump worth it in a 1970s house?", at: Date.now() });
    const { document } = paint({ storage: { "consensio.questionDraft.v1": draft } });
    const field = document.getElementById("questionInput");
    expect(field.value).toBe("Is a heat pump worth it in a 1970s house?");
    expect(field.style.height).toBe("96px");
    expect(document.getElementById("sendButton").disabled).toBe(false);
    const stale = JSON.stringify({ text: "Old question", at: Date.now() - 2 * 24 * 60 * 60 * 1000 });
    expect(paint({ storage: { "consensio.questionDraft.v1": stale } }).document.getElementById("questionInput").value).toBe("");
  });
});

describe("remembering the composer for the next first frame", () => {
  it("keeps the words drawn from the model list when the page is left", () => {
    const { window, document } = paint({ storage: { id_token: token("u1") } });
    window.__consensioAuthState = { known: true, uid: "u1" };
    // The Agent picker as agent-chat.js draws it once the list has loaded.
    document.getElementById("agentModelDropdown").dataset.catalog = "ready";
    chip(document).querySelector(".model-picker-display-text").textContent = "GPT-6 Sol";
    document.getElementById("agentReasoningEffort").innerHTML = '<option value="medium" selected>Medium</option>';
    window.dispatchEvent(new window.Event("pagehide"));
    const look = JSON.parse(window.localStorage.getItem("consensio.firstFrame.v1"));
    expect(look).toMatchObject({ uid: "u1", agentModel: "GPT-6 Sol", agentEffort: "Medium" });
    // A placeholder ("Loading…") is never remembered.
    document.getElementById("agentModelDropdown").dataset.catalog = "loading";
    window.dispatchEvent(new window.Event("pagehide"));
    expect(JSON.parse(window.localStorage.getItem("consensio.firstFrame.v1")).agentModel).toBeUndefined();
    window.App.firstFrame.forget();
    expect(window.localStorage.getItem("consensio.firstFrame.v1")).toBeNull();
  });
});

import { afterEach, describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// static/js/ai-consent.js: the one question before an account's first
// question goes to the AI providers (app/services/ai_consent.py).
const contexts = [];

function boot({ answer = true, saved = true, uid = "u1" } = {}) {
  const calls = { asked: [], posts: [], toasts: [] };
  const ctx = loadScripts(["static/js/ai-consent.js"], {
    before(window) {
      window.auth = { currentUser: uid ? { uid, getIdToken: async () => "token-" + uid } : null };
      window.MODEL_FAMILIES = [
        { label: "OpenAI", citationLabel: "OpenAI" },
        { label: "Anthropic", citationLabel: "Anthropic Claude" },
        { label: "Qwen" },
      ];
      window.fetch = async (url, options) => {
        calls.posts.push([url, options]);
        return { ok: saved };
      };
      window.App = {
        confirm: async options => { calls.asked.push(options); return answer; },
        toast: options => calls.toasts.push(options),
      };
    },
  });
  contexts.push(ctx);
  return { ...ctx, App: ctx.window.App, calls };
}
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

describe("before the first question", () => {
  it("asks nothing while the account's answer is not known: the server is the gate", async () => {
    const { App, calls } = boot();
    expect(await App.aiConsent.ensure()).toBe(true);
    App.aiConsent.set("u1", undefined);
    expect(await App.aiConsent.ensure()).toBe(true);
    App.aiConsent.set("u1", true);
    expect(await App.aiConsent.ensure()).toBe(true);
    expect(calls.asked).toEqual([]);
  });

  it("names the companies, saves the yes once and then sends without asking", async () => {
    const { App, calls } = boot();
    App.aiConsent.set("u1", false);
    expect(await App.aiConsent.ensure()).toBe(true);
    expect(calls.asked).toHaveLength(1);
    expect(calls.asked[0].body).toContain("OpenAI, Anthropic Claude, Qwen");
    expect(calls.asked[0].link.href).toBe("/privacy#providers");
    expect(calls.posts).toEqual([["/api/my/ai-consent", { method: "POST", headers: { Authorization: "Bearer token-u1" } }]]);
    expect(await App.aiConsent.ensure()).toBe(true);
    expect(calls.asked).toHaveLength(1);
  });

  it("sends nothing on Not now and asks again next time", async () => {
    const { App, calls } = boot({ answer: false });
    App.aiConsent.set("u1", false);
    expect(await App.aiConsent.ensure()).toBe(false);
    expect(await App.aiConsent.ensure()).toBe(false);
    expect(calls.asked).toHaveLength(2);
    expect(calls.posts).toEqual([]);
  });

  it("does not send when the yes could not be saved", async () => {
    const { App, calls } = boot({ saved: false });
    App.aiConsent.set("u1", false);
    expect(await App.aiConsent.ensure()).toBe(false);
    expect(calls.toasts[0].tone).toBe("error");
    expect(App.aiConsent.needed()).toBe(true);
  });

  it("asks once for two quick Sends", async () => {
    const { App, calls } = boot();
    App.aiConsent.set("u1", false);
    const both = await Promise.all([App.aiConsent.ensure(), App.aiConsent.ensure()]);
    expect(both).toEqual([true, true]);
    expect(calls.asked).toHaveLength(1);
  });

  it("never asks for another account than the one signed in", async () => {
    const { App, calls } = boot({ uid: "u2" });
    App.aiConsent.set("u1", false);
    expect(await App.aiConsent.ensure()).toBe(true);
    App.aiConsent.set("u2", false);
    App.aiConsent.clear();
    expect(await App.aiConsent.ensure()).toBe(true);
    expect(calls.asked).toEqual([]);
  });
});

describe("a refusal from the server", () => {
  it("makes the next Send ask; any other refusal changes nothing", async () => {
    const { App, calls } = boot();
    App.aiConsent.set("u1", true);
    expect(App.aiConsent.refused({ code: "limit_reached" })).toBe(false);
    expect(App.aiConsent.needed()).toBe(false);
    expect(App.aiConsent.refused({ error_code: "ai_consent_required" })).toBe(true);
    expect(App.aiConsent.needed()).toBe(true);
    expect(await App.aiConsent.ensure()).toBe(true);
    expect(calls.asked).toHaveLength(1);
  });
});

describe("window.sendQuestion", () => {
  function sender({ agent = true, agreed = true } = {}) {
    const calls = { agentSends: 0, asked: 0, prepared: 0 };
    const ctx = loadScripts(["static/js/query-send.js"], {
      body: '<textarea id="questionInput">Is it safe?</textarea><button id="sendButton"></button>',
      before(window) {
        window.App = {
          runRegistry: { visible: () => null, claimStartAction: () => true, getSelectedConversationBasis: () => null },
          composerInvite: { sendAsGuest: () => false },
          agentChat: { isSelected: () => agent, send: async () => { calls.agentSends += 1; } },
          aiConsent: { ensure: async () => { calls.asked += 1; return agreed; } },
          getSelectedModelCount: () => 2,
          usageLimit: { blockIfExhausted: () => false, hide: () => {} },
        };
        window.updateQuestionInputAccess = () => true;
        window.validateInputText = () => true;
        window.fetch = async () => { calls.prepared += 1; return { ok: false, json: async () => ({}) }; };
      },
    });
    contexts.push(ctx);
    return { window: ctx.window, calls };
  }

  it("sends an Agent message only after the yes", async () => {
    const no = sender({ agreed: false });
    await no.window.sendQuestion();
    expect(no.calls).toMatchObject({ asked: 1, agentSends: 0 });
    const yes = sender();
    await yes.window.sendQuestion();
    expect(yes.calls).toMatchObject({ asked: 1, agentSends: 1 });
  });

  it("starts no Compare run without it", async () => {
    const { window, calls } = sender({ agent: false, agreed: false });
    await window.sendQuestion();
    expect(calls).toMatchObject({ asked: 1, prepared: 0 });
    expect(window.document.getElementById("questionInput").value).toBe("Is it safe?");
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// static/js/composer-invite.js: a guest's Send, the send after sign-in, the
// example questions and the source of the "ask" event.
const body = '<textarea id="questionInput"></textarea><button id="sendButton"></button>'
  + '<div id="composerStarters">'
  + '<button type="button" class="composer-starter" data-starter="vat" data-question="Do I charge VAT?">VAT?</button>'
  + '<button type="button" class="composer-starter" data-starter="check" data-question="Check this AI answer:&#10;&#10;">Check</button>'
  + '</div>';
const PENDING = "consensio.sendAfterLogin.v1";
const contexts = [];

function boot({ guest = true, pending = null, basis = null } = {}) {
  const calls = { drafts: [], modals: [], events: [], sends: 0 };
  const ctx = loadScripts(["static/js/composer-invite.js"], {
    body,
    before(window) {
      if (pending) window.localStorage.setItem(PENDING, JSON.stringify(pending));
      window.App = {
        isGuestComposer: () => guest,
        saveQuestionDraft: value => calls.drafts.push(value),
        openAuthModal: (...args) => calls.modals.push(args),
        trackAppEvent: (name, data) => calls.events.push([name, data]),
        runRegistry: { visible: () => null, getSelectedConversationBasis: () => basis },
      };
      window.userCanAskQuestions = () => !guest;
      window.updateQuestionInputAccess = () => {};
      // Like query-send.js: the "ask" (trackAsk) is read while sending.
      window.sendQuestion = async () => {
        calls.sends += 1;
        calls.sentText = window.document.getElementById("questionInput").value;
        calls.ask = window.App.composerInvite.takeAskContext();
      };
    },
  });
  contexts.push(ctx);
  // A deferred bundle runs after parsing; jsdom is still "loading" here.
  ctx.document.dispatchEvent(new ctx.window.Event("DOMContentLoaded"));
  return { ...ctx, App: ctx.window.App, input: ctx.document.getElementById("questionInput"), calls };
}
const tick = window => new Promise(resolve => window.setTimeout(resolve, 5));
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

describe("a guest's Send", () => {
  it("is not handled for an account", () => {
    const { App, calls } = boot({ guest: false });
    expect(App.composerInvite.sendAsGuest()).toBe(false);
    expect(calls.modals).toEqual([]);
  });

  it("keeps the question, remembers the send and opens the sign-up with the reason", () => {
    const { App, input, window, calls } = boot();
    input.value = "  Is creatine safe for teenagers?  ";
    expect(App.composerInvite.sendAsGuest()).toBe(true);
    expect(calls.drafts).toEqual(["Is creatine safe for teenagers?"]);
    const pending = JSON.parse(window.localStorage.getItem(PENDING));
    expect(pending.source).toBe("typed");
    expect(pending.text).toBe("Is creatine safe for teenagers?");
    expect(Date.now() - pending.at).toBeLessThan(5000);
    const [mode, trigger, source, options] = calls.modals[0];
    expect([mode, trigger.id, source]).toEqual(["register", "sendButton", "composer"]);
    expect(options.lead).toMatch(/runs as soon as you're signed in/);
    expect(calls.events).toEqual([["app_guest_send", { source: "typed" }]]);
  });

  it("only points to the field while it is empty", () => {
    const { App, input, document, calls } = boot();
    expect(App.composerInvite.sendAsGuest()).toBe(true);
    expect(document.activeElement).toBe(input);
    expect(calls.modals).toEqual([]);
    expect(calls.drafts).toEqual([]);
  });
});

describe("the send after sign-in", () => {
  it("sends the waiting question once the session can run it, and only once", async () => {
    const { App, input, window, calls } = boot({ guest: false, pending: { at: Date.now() - 60000, source: "example" } });
    input.value = "Do I charge VAT?";
    App.composerInvite.afterAccessUpdate(false);
    await tick(window);
    expect(calls.sends).toBe(0);
    expect(window.localStorage.getItem(PENDING)).not.toBeNull();

    App.composerInvite.afterAccessUpdate(true);
    App.composerInvite.afterAccessUpdate(true);
    expect(window.localStorage.getItem(PENDING)).toBeNull();
    await tick(window);
    expect(calls.sends).toBe(1);
    expect(calls.sentText).toBe("Do I charge VAT?");
    expect(calls.ask).toEqual({ source: "example", after_login: true });
    expect(App.composerInvite.takeAskContext()).toEqual({ source: "typed" });
  });

  it("does not pass the mark on when the send stopped before its ask", async () => {
    const { App, input, window, calls } = boot({ guest: false, pending: { at: Date.now(), source: "typed" } });
    window.sendQuestion = async () => { calls.sends += 1; };
    input.value = "Refused by a limit";
    App.composerInvite.afterAccessUpdate(true);
    await tick(window);
    expect(calls.sends).toBe(1);
    expect(App.composerInvite.takeAskContext()).toEqual({ source: "typed" });
  });

  it.each([
    ["an hour later", { at: Date.now() - 61 * 60000, source: "typed" }, null],
    ["into a chat on screen", { at: Date.now(), source: "typed" }, { chatId: "chat-1" }],
  ])("does not send %s, and forgets the wish", async (_label, pending, basis) => {
    const { App, input, window, calls } = boot({ guest: false, pending, basis });
    input.value = "Kept in the field";
    App.composerInvite.afterAccessUpdate(true);
    await tick(window);
    expect(calls.sends).toBe(0);
    expect(input.value).toBe("Kept in the field");
    expect(window.localStorage.getItem(PENDING)).toBeNull();
  });

  it("sends only the text that was sent, never one typed or cut short after it", async () => {
    const { App, input, window, calls } = boot({ guest: false,
      pending: { at: Date.now(), source: "pasted", text: "A long pasted answer" } });
    input.value = "A long pasted";
    App.composerInvite.afterAccessUpdate(true);
    await tick(window);
    expect(calls.sends).toBe(0);
    expect(input.value).toBe("A long pasted");
    expect(window.localStorage.getItem(PENDING)).toBeNull();
    expect(App.composerInvite.takeAskContext()).toEqual({ source: "typed" });
  });

  it("leaves the send to the tab in front", async () => {
    const pending = { at: Date.now(), source: "typed", text: "Question" };
    const { App, input, window, document, calls } = boot({ guest: false, pending });
    input.value = "Question";
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    App.composerInvite.afterAccessUpdate(true);
    await tick(window);
    expect(calls.sends).toBe(0);
    expect(JSON.parse(window.localStorage.getItem(PENDING))).toEqual(pending);

    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
    App.composerInvite.afterAccessUpdate(true);
    await tick(window);
    expect(calls.sends).toBe(1);
    expect(calls.sentText).toBe("Question");
  });

  it("waits for the fresh page while the sign-in reloads this one", async () => {
    const { App, input, window, calls } = boot({ guest: false, pending: { at: Date.now(), source: "typed" } });
    input.value = "Question";
    App.reloadingAfterSignIn = true;
    App.composerInvite.afterAccessUpdate(true);
    await tick(window);
    expect(calls.sends).toBe(0);
    expect(window.localStorage.getItem(PENDING)).not.toBeNull();
  });
});

describe("example questions and the source of a question", () => {
  it("fill the field without sending and count as an example", () => {
    const { App, input, document, calls } = boot({ guest: false });
    const seen = vi.fn();
    input.addEventListener("input", seen);
    document.querySelector('[data-starter="check"]').click();
    expect(input.value).toBe("Check this AI answer:\n\n");
    expect(input.selectionStart).toBe(input.value.length);
    expect(seen).toHaveBeenCalledTimes(1);
    expect(calls.sends).toBe(0);
    expect(calls.events).toEqual([["app_starter_used", { starter: "check", guest: false }]]);
    expect(App.composerInvite.takeAskContext()).toEqual({ source: "example" });
  });

  it("leave a locked field alone", () => {
    const { input, document, calls } = boot();
    input.disabled = true;
    document.querySelector('[data-starter="vat"]').click();
    expect(input.value).toBe("");
    expect(calls.events).toEqual([]);
  });

  it("call a long paste pasted and a short one typed", () => {
    const { App, input, window } = boot({ guest: false });
    const paste = text => {
      const event = new window.Event("paste", { bubbles: true });
      Object.defineProperty(event, "clipboardData", { value: { getData: () => text } });
      input.dispatchEvent(event);
    };
    paste("Is this right?");
    expect(App.composerInvite.takeAskContext()).toEqual({ source: "typed" });
    paste("An answer from another assistant. ".repeat(8));
    expect(App.composerInvite.takeAskContext()).toEqual({ source: "pasted" });
  });
});

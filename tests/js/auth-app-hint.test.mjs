/**
 * While someone is signed in, the app leaves a bare `consens_app=1` hint so
 * opening consens.io goes straight to /app (routers/pages.py). Signing out
 * removes it, and it never carries the identity.
 */

import { afterEach, describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function boot() {
  const ctx = loadScripts(["static/js/auth-session-state.js"]);
  contexts.push(ctx);
  return ctx;
}

describe("app entry hint", () => {
  it("is set on sign-in and cleared on sign-out, without the uid", () => {
    const { window } = boot();

    window.App.authState.publish("user-123");
    expect(window.document.cookie).toContain("consens_app=1");
    expect(window.document.cookie).not.toContain("user-123");

    window.App.authState.publish(null);
    expect(window.document.cookie).not.toContain("consens_app=1");
  });
});

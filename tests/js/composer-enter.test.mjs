import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// Enter follows the device, not the window's width (Apple-Audit E7), and an
// Enter that confirms an input method's word is never a send (E8).
function boot({ touch = false } = {}) {
  return loadScripts(["static/js/app-core.js"], {
    before(window) {
      window.matchMedia = query => ({ matches: touch && query.includes("pointer: coarse"), addEventListener() {} });
    },
  });
}
const key = (window, init) => new window.KeyboardEvent("keydown", { key: "Enter", ...init });

describe("Enter in the composer", () => {
  it("sends with a keyboard, also in a narrow window, and breaks the line with Shift", () => {
    const { window } = boot();
    window.innerWidth = 600;
    expect(window.App.enterSends(key(window, {}))).toBe(true);
    expect(window.App.enterSends(key(window, { shiftKey: true }))).toBe(false);
    expect(window.App.enterSends(new window.KeyboardEvent("keydown", { key: "a" }))).toBe(false);
  });

  it("is a new paragraph on a touch keyboard, whatever the width", () => {
    const { window } = boot({ touch: true });
    window.innerWidth = 1024;
    expect(window.App.enterSends(key(window, {}))).toBe(false);
  });

  it("belongs to the word an input method is composing, also Safari's keyCode 229", () => {
    const { window } = boot();
    expect(window.App.isComposingKey(key(window, { isComposing: true }))).toBe(true);
    expect(window.App.isComposingKey(key(window, { keyCode: 229 }))).toBe(true);
    expect(window.App.enterSends(key(window, { keyCode: 229 }))).toBe(false);
    expect(window.App.isComposingKey(key(window, {}))).toBe(false);
  });
});

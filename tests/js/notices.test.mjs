import { afterEach, describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * One notice system (Apple audit E3) and the app's own confirmation (E1):
 *   - App.toast queues instead of stacking, is read out (role=status), stays
 *     as long as it takes to read, keeps an error until it is closed, and
 *     pauses under the pointer;
 *   - App.undoNotice (chat deletion, Apple audit E2) is a thin forward: the
 *     way back first, the step itself only once the line ran out;
 *   - App.composerNotice says an input mistake at the composer;
 *   - App.confirm answers with a promise instead of window.confirm.
 */
const contexts = [];
afterEach(() => {
  vi.useRealTimers();
  contexts.splice(0).forEach(ctx => ctx.window.close());
});

function boot(body = "") {
  const ctx = loadScripts(
    ["static/js/motion.js", "static/js/modal-dialog.js", "static/js/notices.js", "static/js/confirm-dialog.js"],
    {
      body,
      before(window) { window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} }); },
    }
  );
  contexts.push(ctx);
  return ctx;
}

const line = document => document.querySelector("#appToasts .toast.is-shown");

describe("App.toast", () => {
  it("reads out one line at a time and lets the next wait its turn", () => {
    vi.useFakeTimers();
    const { window, document } = boot();
    window.App.toast({ message: "Link copied to clipboard." });
    window.App.toast({ message: "Share link revoked." });
    const region = document.getElementById("appToasts");
    expect(region.getAttribute("role")).toBe("status");
    expect(region.getAttribute("aria-live")).toBe("polite");
    expect(document.querySelectorAll("#appToasts .toast.is-shown")).toHaveLength(1);
    expect(line(document).textContent).toContain("Link copied");
    // The first is seen before the second takes its place.
    vi.advanceTimersByTime(1000);
    expect(line(document).textContent).toContain("Link copied");
    vi.advanceTimersByTime(700);
    expect(line(document).textContent).toContain("Share link revoked");
  });

  it("stays as long as it takes to read", () => {
    vi.useFakeTimers();
    const { window } = boot();
    window.App.toast({ message: "Saved." });
    vi.advanceTimersByTime(2900);
    expect(window.App.toast.current()).not.toBeNull();
    vi.advanceTimersByTime(200);
    expect(window.App.toast.current()).toBeNull();

    const long = "Logout could not be completed. You are still signed in. Please try again in a moment, or reload the page first.";
    window.App.toast({ message: long });
    vi.advanceTimersByTime(4000);
    expect(window.App.toast.current()).not.toBeNull();
  });

  it("keeps an error until it is closed", () => {
    vi.useFakeTimers();
    const { window, document } = boot();
    window.App.toast({ message: "Revoking failed: offline", tone: "error" });
    vi.advanceTimersByTime(60000);
    const shown = line(document);
    expect(shown.dataset.tone).toBe("error");
    const close = shown.querySelector(".toast-close");
    expect(close.hidden).toBe(false);
    expect(close.querySelector("svg.close-icon")).not.toBeNull();
    close.click();
    expect(window.App.toast.current()).toBeNull();
  });

  it("restarts the same words instead of queueing a copy", () => {
    vi.useFakeTimers();
    const { window, document } = boot();
    window.App.toast({ message: "Link copied to clipboard." });
    vi.advanceTimersByTime(2000);
    window.App.toast({ message: "Link copied to clipboard." });
    vi.advanceTimersByTime(2000);
    expect(document.querySelectorAll("#appToasts .toast")).toHaveLength(1);
    expect(window.App.toast.current()).not.toBeNull();
  });

  it("goes inside an open modal dialog, where its Undo can still be pressed", () => {
    const { window, document } = boot('<dialog id="settings" class="modal" open><button>x</button></dialog>');
    window.App.toast({ message: "Memory deleted", undo: () => {} });
    expect(document.getElementById("appToasts").parentElement.id).toBe("settings");
  });
});

describe("App.undoNotice (forwards to App.toast)", () => {
  it("runs the step only when the line runs out, and Undo instead of it", () => {
    vi.useFakeTimers();
    const { window, document } = boot();
    const notices = window.App.undoNotice;
    const first = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "Chat deleted", duration: 5000, ...first });
    expect(line(document).textContent).toContain("Chat deleted");
    vi.advanceTimersByTime(4900);
    expect(first.onExpire).not.toHaveBeenCalled();
    vi.advanceTimersByTime(200);
    expect(first.onExpire).toHaveBeenCalledOnce();
    expect(first.onAction).not.toHaveBeenCalled();

    const second = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "Chat deleted", ...second });
    line(document).querySelector(".toast-action").click();
    expect(second.onAction).toHaveBeenCalledOnce();
    vi.advanceTimersByTime(10000);
    expect(second.onExpire).not.toHaveBeenCalled();
  });

  it("settles the line before it when a new one comes, and pauses while pointed at", () => {
    vi.useFakeTimers();
    const { window, document } = boot();
    const notices = window.App.undoNotice;
    const first = { onAction: vi.fn(), onExpire: vi.fn() };
    const second = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "One", ...first });
    notices.show({ text: "Two", duration: 3000, ...second });
    expect(first.onExpire).toHaveBeenCalledOnce();
    const shown = line(document);
    shown.dispatchEvent(new window.Event("pointerenter"));
    vi.advanceTimersByTime(10000);
    expect(second.onExpire).not.toHaveBeenCalled();
    shown.dispatchEvent(new window.Event("pointerleave"));
    vi.advanceTimersByTime(3100);
    expect(second.onExpire).toHaveBeenCalledOnce();
    // settle() and cancel() end it now.
    const third = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "Three", ...third }).cancel();
    expect(third.onExpire).not.toHaveBeenCalled();
    const fourth = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "Four", ...fourth }).settle();
    expect(fourth.onExpire).toHaveBeenCalledOnce();
    expect(notices.current()).toBeNull();
  });

  it("waits for an asynchronous action and lets it say how it went", async () => {
    const { window, document } = boot();
    let finish;
    const handle = window.App.toast({
      message: "Memory updated",
      action: { label: "Undo", onAction: h => new Promise(resolve => { finish = () => { h.update({ message: "Previous Memory restored", action: null }); resolve(); }; }) },
    });
    line(document).querySelector(".toast-action").click();
    expect(line(document).querySelector(".toast-action").disabled).toBe(true);
    finish();
    await Promise.resolve();
    await Promise.resolve();
    expect(line(document).textContent).toContain("Previous Memory restored");
    expect(line(document).querySelector(".toast-action").hidden).toBe(true);
    handle.cancel();
  });
});

describe("App.composerNotice", () => {
  it("says the mistake under the field and goes when the field changes", () => {
    const { window, document } = boot(`
      <textarea id="questionInput"></textarea>
      <div id="agentComposerNotice" hidden></div>`);
    window.App.composerNotice.show("Your message is longer than 8,000 characters.");
    const notice = document.getElementById("composerInputNotice");
    expect(notice.hidden).toBe(false);
    expect(notice.getAttribute("role")).toBe("alert");
    expect(notice.previousElementSibling.id).toBe("agentComposerNotice");
    expect(document.getElementById("questionInput").getAttribute("aria-describedby")).toContain("composerInputNotice");
    document.getElementById("questionInput").dispatchEvent(new window.Event("input", { bubbles: true }));
    expect(notice.hidden).toBe(true);
    expect(document.getElementById("questionInput").hasAttribute("aria-describedby")).toBe(false);
  });
});

describe("App.confirm", () => {
  it("answers true for its button and false for Cancel, with focus on Cancel when it destroys", async () => {
    const { window, document } = boot('<button id="opener">Delete</button>');
    document.getElementById("opener").focus();
    const asked = window.App.confirm({ title: "Delete your account?", body: "This cannot be undone.", confirmLabel: "Delete account", danger: true });
    const dialog = document.getElementById("appConfirmDialog");
    expect(dialog.open).toBe(true);
    expect(dialog.querySelector("h2").textContent).toBe("Delete your account?");
    expect(document.activeElement.textContent).toBe("Cancel");
    dialog.querySelector(".confirm-accept").click();
    await expect(asked).resolves.toBe(true);
    expect(dialog.open).toBe(false);
    expect(document.activeElement.id).toBe("opener");

    const again = window.App.confirm({ title: "Revoke this public link?", confirmLabel: "Revoke" });
    expect(document.activeElement.textContent).toBe("Revoke");
    dialog.querySelector(".confirm-cancel").click();
    await expect(again).resolves.toBe(false);
  });
});

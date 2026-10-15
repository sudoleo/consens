/**
 * The "Send feedback" dialog (audit F7).
 *
 * Before: the button opened a form for guests too, whose submit then failed
 * with a German alert(); a failed request was read as success-shaped JSON
 * (no response.ok check), and a double click sent the message twice.
 * Now a guest sees a login hint and the contact address, a member's send
 * reports in the dialog's own status line in English, and the button stays
 * locked while a send is in flight.
 */

import { describe, expect, it, vi } from "vitest";

import { bootApp, settle, templateSlice } from "./helpers/appBoot.mjs";

const BODY = `
  <button id="toggleSidebarButton" class="sidebar-toggle" type="button"></button>
  <aside class="sidebar">
    <div class="bookmarks-section"><button id="bookmarksToggle" type="button"></button><div id="bookmarksContainer"></div></div>
    <button type="button" id="feedbackButton" aria-label="Send feedback">Feedback</button>
  </aside>
  <a id="logoLink" href="#home"></a>
  <input id="reasoningToggle" type="checkbox">
  <textarea id="questionInput"></textarea>
  <button id="sendButton" type="button"></button>
  <input id="openrouterKey">
` + templateSlice('id="feedbackModal"', "</dialog>");

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function response(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

async function boot({ user = null, fetchImpl } = {}) {
  const booted = await bootApp({
    body: BODY,
    before(window) {
      window.auth = { currentUser: user };
      window.App = window.App || {};
      window.App.openAuthModal = vi.fn();
    },
  });
  if (fetchImpl) booted.window.fetch = fetchImpl;
  // console.error from a failed send is expected noise here.
  booted.window.console.error = () => {};
  return booted;
}

function member() {
  return { uid: "u1", getIdToken: vi.fn(async () => "id-token") };
}

function submit(window, document, message, email = "") {
  const form = document.getElementById("feedbackForm");
  form.elements.message.value = message;
  form.elements.email.value = email;
  form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
  return form;
}

describe("feedback dialog for guests", () => {
  it("shows the login hint instead of a form that can only fail", async () => {
    const { window, document, errors } = await boot();
    const button = document.getElementById("feedbackButton");
    button.focus();
    button.click();

    const dialog = document.getElementById("feedbackModal");
    expect(dialog.open).toBe(true);
    expect(document.getElementById("feedbackGuestNote").hidden).toBe(false);
    expect(document.getElementById("feedbackForm").hidden).toBe(true);
    expect(document.activeElement).toBe(document.getElementById("feedbackLoginButton"));
    expect(document.querySelector('#feedbackGuestNote a[href="mailto:contact@consens.io"]')).not.toBeNull();

    // Log in closes this dialog first, then opens the login dialog with the
    // feedback button as the control focus returns to.
    document.getElementById("feedbackLoginButton").click();
    expect(dialog.open).toBe(false);
    expect(window.App.openAuthModal).toHaveBeenCalledWith("login", button, "feedback");
    expect(errors).toEqual([]);
    window.close();
  });
});

describe("feedback dialog for members", () => {
  it("sends once, locks the button meanwhile and confirms inline", async () => {
    const pending = deferred();
    const fetch = vi.fn(() => pending.promise);
    const { window, document, errors } = await boot({ user: member(), fetchImpl: fetch });
    const alert = vi.fn();
    window.alert = alert;

    document.getElementById("feedbackButton").click();
    expect(document.getElementById("feedbackForm").hidden).toBe(false);
    expect(document.activeElement).toBe(document.querySelector('#feedbackForm textarea[name="message"]'));

    const form = submit(window, document, "  Great app  ", "me@example.com");
    const sendButton = form.querySelector('button[type="submit"]');
    await settle(window);
    expect(sendButton.disabled).toBe(true);
    expect(form.getAttribute("aria-busy")).toBe("true");

    // A second submit while the first is in flight sends nothing.
    form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
    await settle(window);
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/feedback");
    expect(JSON.parse(init.body)).toEqual({ message: "Great app", email: "me@example.com", id_token: "id-token" });

    pending.resolve(response(200, { status: "success" }));
    await settle(window);
    const status = document.getElementById("feedbackStatus");
    expect(status.hidden).toBe(false);
    expect(status.textContent).toBe("Thanks, your feedback was sent.");
    expect(status.dataset.tone).toBeUndefined();
    expect(sendButton.disabled).toBe(false);
    expect(form.elements.message.value).toBe("");
    expect(alert).not.toHaveBeenCalled();
    expect(errors).toEqual([]);
    window.close();
  });

  it("reports a refused send in English instead of treating it as success", async () => {
    const fetch = vi.fn(async () => response(429, { detail: "Please wait before sending feedback again." }));
    const { window, document } = await boot({ user: member(), fetchImpl: fetch });
    document.getElementById("feedbackButton").click();
    const form = submit(window, document, "Second message");
    await settle(window);
    await settle(window);
    const status = document.getElementById("feedbackStatus");
    expect(status.textContent).toBe("Please wait before sending feedback again.");
    expect(status.dataset.tone).toBe("error");
    // The message stays for a retry.
    expect(form.elements.message.value).toBe("Second message");
    expect(form.querySelector('button[type="submit"]').disabled).toBe(false);
    window.close();
  });

  it("turns a validation list into one readable sentence", async () => {
    const fetch = vi.fn(async () => response(422, {
      detail: [{ msg: "Value error, Enter a valid e-mail address." }],
    }));
    const { window, document } = await boot({ user: member(), fetchImpl: fetch });
    document.getElementById("feedbackButton").click();
    submit(window, document, "Hello", "not-an-address");
    await settle(window);
    await settle(window);
    expect(document.getElementById("feedbackStatus").textContent).toBe("Enter a valid e-mail address.");
    window.close();
  });

  it("explains a network failure and an empty message without a request", async () => {
    const fetch = vi.fn(async () => { throw new TypeError("Failed to fetch"); });
    const { window, document } = await boot({ user: member(), fetchImpl: fetch });
    document.getElementById("feedbackButton").click();

    submit(window, document, "   ");
    await settle(window);
    expect(fetch).not.toHaveBeenCalled();
    expect(document.getElementById("feedbackStatus").textContent).toBe("Please write a message first.");

    submit(window, document, "Hello");
    await settle(window);
    await settle(window);
    expect(document.getElementById("feedbackStatus").textContent)
      .toBe("Your feedback could not be sent. Check your connection and try again.");
    window.close();
  });

  it("keeps a typed message on a backdrop click; Escape still closes", async () => {
    const { window, document } = await boot({ user: member() });
    const dialog = document.getElementById("feedbackModal");
    document.getElementById("feedbackButton").click();
    document.querySelector('#feedbackForm textarea[name="message"]').value = "Half a thought";

    dialog.dispatchEvent(new window.MouseEvent("pointerdown", { bubbles: true }));
    dialog.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    expect(dialog.open).toBe(true);

    document.activeElement.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    expect(dialog.open).toBe(false);
    expect(document.activeElement).toBe(document.getElementById("feedbackButton"));
    window.close();
  });
});

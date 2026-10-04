/**
 * Saved memories: the Settings list (user-memory.js) and the "Memory updated"
 * note under an Agent answer (agent-memory.js).
 */
import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const SETTINGS = `
  <section id="memorySettingsSection">
    <input type="checkbox" id="memoryEnabledSwitch">
    <input type="checkbox" id="memoryAutoSwitch">
    <ul id="memoryItemsList"></ul>
    <p id="memoryItemsEmpty">Nothing saved yet.</p>
    <form id="memoryItemAddForm"><input type="text" id="memoryItemInput"><button id="memoryItemAddBtn" type="submit">Add</button></form>
    <span id="memoryItemsCount"></span>
    <button id="clearMemoryItemsBtn" type="button">Delete all</button>
    <span id="memoryItemsStatus"></span>
    <textarea id="memoryRoleInput" maxlength="250"></textarea>
    <textarea id="memoryFocusInput" maxlength="250"></textarea>
    <textarea id="memoryStyleInput" maxlength="250"></textarea>
    <textarea id="memoryConstraintsInput" maxlength="250"></textarea>
    <textarea id="memoryNotesInput" maxlength="800"></textarea>
    <button id="saveMemoryBtn" type="button">Save memory</button>
    <button id="clearMemoryBtn" type="button">Clear</button>
    <p id="memoryStatus"></p>
  </section>
  <button id="editSystemPromptBtn" type="button">Settings</button>
`;

async function settle() {
  for (let i = 0; i < 20; i += 1) await Promise.resolve();
}

function bootSettings() {
  const server = {
    profile: { schema_version: 2, enabled: true, auto_memory: false, role: "Nurse", focus: "", style: "", constraints: "", notes: "" },
    revision: 3,
    items: [{ id: "m1a2b3c", text: "Prefers tea.", origin: "agent", created_at: "2026-10-01T10:00:00+00:00", updated_at: "2026-10-01T10:00:00+00:00" }],
    itemsRevision: 7,
    calls: [],
  };
  const { window, document, dom } = loadScripts(["static/js/user-memory.js"], {
    body: SETTINGS,
    before(win) {
      win.auth = { currentUser: { uid: "uid-1", getIdToken: async () => "token" } };
      win.fetch = async (url, options = {}) => {
        const body = options.body ? JSON.parse(options.body) : null;
        server.calls.push({ url, method: options.method || "GET", body });
        const ok = data => ({ ok: true, status: 200, json: async () => data });
        const listing = () => ({ items: server.items, items_revision: server.itemsRevision, limits: { items: 100, item_chars: 300 } });
        if (url === "/api/my/memory/items" && options.method === "POST") {
          if (body.expected_revision !== server.itemsRevision) {
            return { ok: false, status: 409, json: async () => ({ error: { error_code: "revision_conflict", message: "Changed.", revision: server.itemsRevision } }) };
          }
          for (const change of body.changes) {
            if (change.op === "add") server.items = [...server.items, { id: "m9f8e7d", text: change.text, origin: "user" }];
            if (change.op === "delete") server.items = server.items.filter(item => item.id !== change.id);
            if (change.op === "update") server.items = server.items.map(item => item.id === change.id ? { ...item, text: change.text, origin: "user" } : item);
          }
          server.itemsRevision += 1;
          return ok({ status: "success", ...listing() });
        }
        if (url === "/api/my/memory/items" && options.method === "DELETE") {
          server.items = [];
          server.itemsRevision += 1;
          return ok({ status: "success", ...listing() });
        }
        if (options.method === "PUT") {
          const { expected_revision: _ignored, ...fields } = body;
          server.profile = { schema_version: 2, ...fields };
          server.revision += 1;
          return ok({ memory: server.profile, revision: server.revision });
        }
        return ok({ memory: server.profile, revision: server.revision, ...listing() });
      };
    },
  });
  document.dispatchEvent(new window.Event("DOMContentLoaded"));
  return { window, document, dom, server };
}

async function open(ctx) {
  ctx.document.getElementById("editSystemPromptBtn").click();
  await settle();
}

describe("Settings: Let Agent update memory", () => {
  it("saves only the switch and keeps the text fields", async () => {
    const ctx = bootSettings();
    await open(ctx);
    const auto = ctx.document.getElementById("memoryAutoSwitch");
    expect(auto.checked).toBe(false);
    ctx.document.getElementById("memoryRoleInput").value = "Half-typed draft";
    auto.checked = true;
    auto.dispatchEvent(new ctx.window.Event("change"));
    await settle();
    const put = ctx.server.calls.find(call => call.method === "PUT");
    expect(put.body.auto_memory).toBe(true);
    expect(put.body.role).toBe("Nurse");
    expect(put.body.expected_revision).toBe(3);
    expect(ctx.document.getElementById("memoryRoleInput").value).toBe("Half-typed draft");
    // Saving the form later keeps the switch on.
    ctx.document.getElementById("saveMemoryBtn").click();
    await settle();
    expect(ctx.server.calls.filter(call => call.method === "PUT").at(-1).body.auto_memory).toBe(true);
    ctx.dom.window.close();
  });

  it("is unavailable while memory itself is paused", async () => {
    const ctx = bootSettings();
    ctx.server.profile = { ...ctx.server.profile, enabled: false };
    await open(ctx);
    expect(ctx.document.getElementById("memoryAutoSwitch").disabled).toBe(true);
    ctx.dom.window.close();
  });
});

describe("Settings: saved memories", () => {
  it("lists, adds, edits and deletes memories against the list revision", async () => {
    const ctx = bootSettings();
    await open(ctx);
    const list = ctx.document.getElementById("memoryItemsList");
    expect(list.textContent).toContain("Prefers tea.");
    expect(list.textContent).toContain("Saved by Agent");
    expect(ctx.document.getElementById("memoryItemsEmpty").hidden).toBe(true);

    ctx.document.getElementById("memoryItemInput").value = "Lives in Munich.";
    ctx.document.getElementById("memoryItemAddForm").dispatchEvent(new ctx.window.Event("submit", { cancelable: true }));
    await settle();
    const add = ctx.server.calls.find(call => call.method === "POST");
    expect(add.body).toEqual({ changes: [{ op: "add", text: "Lives in Munich." }], expected_revision: 7 });
    expect(list.textContent).toContain("Lives in Munich.");
    expect(ctx.document.getElementById("memoryItemInput").value).toBe("");

    const row = list.querySelector('[data-item-id="m1a2b3c"]');
    [...row.querySelectorAll("button")].find(button => button.textContent === "Edit").click();
    const input = list.querySelector('[data-item-id="m1a2b3c"] input');
    input.value = "Prefers green tea.";
    [...list.querySelectorAll('[data-item-id="m1a2b3c"] button')].find(button => button.textContent === "Save").click();
    await settle();
    expect(ctx.server.calls.at(-1).body.changes).toEqual([{ op: "update", id: "m1a2b3c", text: "Prefers green tea." }]);
    expect(list.textContent).toContain("Prefers green tea.");

    [...list.querySelectorAll('[data-item-id="m1a2b3c"] button')].find(button => button.textContent === "Delete").click();
    await settle();
    expect(list.textContent).not.toContain("green tea");
    ctx.dom.window.close();
  });

  it("reloads the list instead of overwriting when Agent wrote in between", async () => {
    const ctx = bootSettings();
    await open(ctx);
    ctx.server.itemsRevision = 9;
    ctx.server.items = [...ctx.server.items, { id: "m0000aa", text: "Saved by a run in another tab.", origin: "agent" }];
    ctx.document.getElementById("memoryItemInput").value = "New";
    ctx.document.getElementById("memoryItemAddForm").dispatchEvent(new ctx.window.Event("submit", { cancelable: true }));
    await settle();
    expect(ctx.document.getElementById("memoryItemsStatus").dataset.tone).toBe("error");
    expect(ctx.document.getElementById("memoryItemsList").textContent).toContain("Saved by a run in another tab.");
    ctx.dom.window.close();
  });

  it("asks once before deleting every memory", async () => {
    const ctx = bootSettings();
    await open(ctx);
    const clear = ctx.document.getElementById("clearMemoryItemsBtn");
    clear.click();
    await settle();
    expect(ctx.server.calls.some(call => call.method === "DELETE")).toBe(false);
    expect(clear.textContent).toContain("Delete all saved memories?");
    clear.click();
    await settle();
    expect(ctx.server.calls.some(call => call.method === "DELETE")).toBe(true);
    expect(ctx.document.getElementById("memoryItemsEmpty").hidden).toBe(false);
    ctx.dom.window.close();
  });
});

describe("Memory updated under an answer", () => {
  const CHANGE = "0123456789abcdef";

  function bootNote() {
    const calls = [];
    const ctx = loadScripts(["static/js/agent-memory.js"], {
      body: '<div><div id="answer"></div></div><button id="editSystemPromptBtn"></button>',
      before(win) {
        win.auth = { currentUser: { uid: "uid-1", getIdToken: async () => "token" } };
        win.fetch = vi.fn(async (url, options) => {
          calls.push({ url, method: options.method });
          return { ok: true, status: 200, json: async () => ({ status: "success" }) };
        });
      },
    });
    return { ...ctx, calls };
  }

  it("shows each change and undoes them with one request per change", async () => {
    const { window: w, document: d, dom, calls } = bootNote();
    const body = d.getElementById("answer");
    const changed = vi.fn();
    w.addEventListener("consensio:memory-changed", changed);
    w.App.agentMemory.render(body, { key: "turn", running: true, changes: [
      { change_id: CHANGE, op: "update", item_id: "m1a2b3c", text: "Lives in Munich.", undone: false },
      { change_id: CHANGE, op: "add", item_id: "m4d5e6f", text: "Has a dog.", undone: false },
      { change_id: CHANGE, op: "noop", item_id: "m7a8b9c", text: "Ignored." },
    ] });
    const note = body.nextElementSibling;
    expect(note.classList.contains("agent-memory-note")).toBe(true);
    expect(note.textContent).toContain("Memory updated");
    expect(note.textContent).toContain("Updated: Lives in Munich.");
    expect(note.textContent).toContain("Saved: Has a dog.");
    expect(note.textContent).not.toContain("Ignored.");
    [...note.querySelectorAll("button")].find(button => button.textContent === "Undo").click();
    await vi.waitFor(() => expect(note.textContent).toContain("Memory change undone"));
    expect(calls).toEqual([{ url: `/api/my/memory/changes/${CHANGE}/undo`, method: "POST" }]);
    expect(changed).toHaveBeenCalled();
    // A re-render from the (older) saved turn does not offer Undo again.
    w.App.agentMemory.render(body, { key: "turn", running: true, changes: [
      { change_id: CHANGE, op: "add", item_id: "m4d5e6f", text: "Has a dog.", undone: false }] });
    expect([...note.querySelectorAll("button")].find(button => button.textContent === "Undo").hidden).toBe(true);
    // The final answer carries no note.
    w.App.agentMemory.render(body, { key: "turn", changes: [
      { change_id: CHANGE, op: "add", item_id: "m4d5e6f", text: "Has a dog.", undone: false }] });
    expect(body.nextElementSibling).toBeNull();
    dom.window.close();
  });

  it("stays hidden without changes and merges live events", () => {
    const { window: w, document: d, dom } = bootNote();
    const body = d.getElementById("answer");
    w.App.agentMemory.render(body, { key: "turn", running: true, changes: [] });
    expect(body.nextElementSibling.hidden).toBe(true);
    const list = w.App.agentMemory.receive([], { changes: [{ change_id: CHANGE, op: "add", item_id: "m1a2b3c", text: "Likes tea." }] });
    w.App.agentMemory.receive(list, { changes: [{ change_id: CHANGE, op: "add", item_id: "m1a2b3c", text: "Likes tea." }] });
    expect(list).toHaveLength(1);
    dom.window.close();
  });
});

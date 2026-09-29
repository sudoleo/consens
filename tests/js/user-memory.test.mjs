/**
 * user-memory.js -- der Schalter "Use my memory".
 *
 * Der Server antwortet mit dem gespeicherten Profil INKLUSIVE seiner
 * schema_version, und PUT /api/my/memory verbietet unbekannte Felder. Wer die
 * Antwort ungefiltert zurueckschickt, bekommt 422 -- und der Schalter sprang
 * genau deshalb in seine alte Stellung zurueck. Diese Tests halten fest, dass
 * der Body nur die Felder der Schnittstelle enthaelt.
 */

import { beforeEach, describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const SETTINGS = `
  <section id="memorySettingsSection">
    <label for="memoryEnabledSwitch"><input type="checkbox" id="memoryEnabledSwitch"></label>
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

// Was der Server tatsaechlich liefert: sanitize_profile() setzt schema_version.
function storedProfile(enabled) {
  return {
    schema_version: 2,
    enabled,
    role: "Anaesthetist",
    focus: "",
    style: "",
    constraints: "",
    notes: "A note the user maintains."
  };
}

function boot() {
  const calls = [];
  const { window, document } = loadScripts(["static/js/user-memory.js"], {
    body: SETTINGS,
    before(win) {
      win.auth = { currentUser: { uid: "uid-1", getIdToken: async () => "token" } };
      win.fetch = async (url, options = {}) => {
        const body = options.body ? JSON.parse(options.body) : null;
        calls.push({ url, method: options.method, body });
        // Der Server spiegelt nur bekannte Felder zurueck; unbekannte lehnt er
        // mit 422 ab. Genau dieses Verhalten bildet der Stub nach.
        if (options.method === "PUT") {
          const unknown = Object.keys(body).filter(
            key => !["enabled", "role", "focus", "style", "constraints", "notes", "expected_revision"].includes(key)
          );
          if (unknown.length) {
            return {
              ok: false,
              status: 422,
              json: async () => ({
                detail: unknown.map(key => ({ type: "extra_forbidden", loc: ["body", key] }))
              })
            };
          }
          return {
            ok: true,
            status: 200,
            json: async () => ({ memory: storedProfile(body.enabled), revision: body.expected_revision + 1, limits: { notes_chars: 800 } })
          };
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({ memory: storedProfile(true), revision: 4, limits: { notes_chars: 800 } })
        };
      };
    }
  });
  return { window, document, calls };
}

async function settle() {
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
}

describe("memory switch", () => {
  let ctx;
  beforeEach(async () => {
    ctx = boot();
    // jsdom steht beim Einfuegen der Skripte noch auf readyState "loading";
    // das Modul bindet sich erst mit DOMContentLoaded, genau wie im Browser.
    ctx.document.dispatchEvent(new ctx.window.Event("DOMContentLoaded"));
    ctx.document.getElementById("editSystemPromptBtn").click();
    await settle();
  });

  it("loads the stored profile into the form", () => {
    expect(ctx.document.getElementById("memoryEnabledSwitch").checked).toBe(true);
    expect(ctx.document.getElementById("memoryRoleInput").value).toBe("Anaesthetist");
  });

  it("turns memory off and stays off", async () => {
    const box = ctx.document.getElementById("memoryEnabledSwitch");
    box.checked = false;
    box.dispatchEvent(new ctx.window.Event("change"));
    await settle();

    const put = ctx.calls.find(call => call.method === "PUT");
    expect(put).toBeTruthy();
    expect(put.body.enabled).toBe(false);
    expect(Object.keys(put.body).sort()).toEqual(
      ["constraints", "enabled", "expected_revision", "focus", "notes", "role", "style"]
    );
    // The switch writes against the revision it loaded (compare-and-swap).
    expect(put.body.expected_revision).toBe(4);
    expect(box.checked).toBe(false);
  });

  it("keeps the saved text when only the switch is written", async () => {
    const box = ctx.document.getElementById("memoryEnabledSwitch");
    box.checked = false;
    box.dispatchEvent(new ctx.window.Event("change"));
    await settle();

    const put = ctx.calls.find(call => call.method === "PUT");
    expect(put.body.role).toBe("Anaesthetist");
    expect(put.body.notes).toBe("A note the user maintains.");
  });
});

/**
 * R12: a stale editor (second tab, or Memory changed by Remember/Correct)
 * gets 409 from the server. The draft must survive, and the user chooses
 * between loading the newer Memory and keeping the draft deliberately.
 */
describe("memory save conflicts", () => {
  function bootWithServer() {
    const server = { revision: 4, profile: storedProfile(true), puts: [] };
    const { window, document } = loadScripts(["static/js/user-memory.js"], {
      body: SETTINGS,
      before(win) {
        win.auth = { currentUser: { uid: "uid-1", getIdToken: async () => "token" } };
        win.fetch = async (url, options = {}) => {
          if (options.method === "PUT") {
            const body = JSON.parse(options.body);
            server.puts.push(body);
            if (body.expected_revision !== server.revision) {
              return {
                ok: false,
                status: 409,
                json: async () => ({
                  detail: {
                    error_code: "revision_conflict",
                    message: "Memory changed in another tab or through Remember/Correct memory. Your draft was not saved.",
                    revision: server.revision
                  }
                })
              };
            }
            const { expected_revision: _ignored, ...fields } = body;
            server.revision += 1;
            server.profile = { schema_version: 2, ...fields };
            return { ok: true, status: 200, json: async () => ({ memory: server.profile, revision: server.revision }) };
          }
          return { ok: true, status: 200, json: async () => ({ memory: server.profile, revision: server.revision }) };
        };
      }
    });
    document.dispatchEvent(new window.Event("DOMContentLoaded"));
    return { window, document, server };
  }

  async function openSettings(ctx) {
    ctx.document.getElementById("editSystemPromptBtn").click();
    await settle();
  }

  function type(ctx, id, value) {
    const input = ctx.document.getElementById(id);
    input.value = value;
    input.dispatchEvent(new ctx.window.Event("input"));
  }

  it("keeps the draft and offers reload when another writer won", async () => {
    const ctx = bootWithServer();
    await openSettings(ctx);
    // Another tab (or an AI edit) saves first.
    ctx.server.revision = 5;
    ctx.server.profile = { ...storedProfile(true), role: "Newer from tab two" };

    type(ctx, "memoryRoleInput", "My unsaved draft");
    ctx.document.getElementById("saveMemoryBtn").click();
    await settle();

    expect(ctx.server.puts[0].expected_revision).toBe(4);
    expect(ctx.server.profile.role).toBe("Newer from tab two");
    expect(ctx.document.getElementById("memoryRoleInput").value).toBe("My unsaved draft");
    const status = ctx.document.getElementById("memoryStatus");
    expect(status.dataset.tone).toBe("error");
    expect(status.querySelector("[data-memory-conflict='reload']")).toBeTruthy();

    status.querySelector("[data-memory-conflict='reload']").click();
    await settle();
    expect(ctx.document.getElementById("memoryRoleInput").value).toBe("Newer from tab two");
  });

  it("can deliberately overwrite the newer Memory with the kept draft", async () => {
    const ctx = bootWithServer();
    await openSettings(ctx);
    ctx.server.revision = 5;
    type(ctx, "memoryRoleInput", "My unsaved draft");
    ctx.document.getElementById("saveMemoryBtn").click();
    await settle();

    ctx.document.querySelector("[data-memory-conflict='keep']").click();
    ctx.document.getElementById("saveMemoryBtn").click();
    await settle();

    expect(ctx.server.puts.map(put => put.expected_revision)).toEqual([4, 5]);
    expect(ctx.server.profile.role).toBe("My unsaved draft");
  });

  it("an AI edit reload does not wipe an unsaved settings draft", async () => {
    const ctx = bootWithServer();
    await openSettings(ctx);
    type(ctx, "memoryNotesInput", "Half-typed note");
    ctx.server.revision = 5;

    await ctx.window.App.userMemory.load(true, { keepDraft: true });

    expect(ctx.document.getElementById("memoryNotesInput").value).toBe("Half-typed note");
    ctx.document.getElementById("saveMemoryBtn").click();
    await settle();
    expect(ctx.server.puts[0].expected_revision).toBe(4);
    expect(ctx.document.getElementById("memoryStatus").querySelector("[data-memory-conflict]")).toBeTruthy();
  });
});

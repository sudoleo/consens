import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// Where the workspace's browser is logged in (agent-sign-ins.js), in
// Settings → Connections: the sites the Agent noted, each of which can go.
function setup() {
  const app = loadScripts(["static/js/agent-sign-ins.js"], { body: '<div id="agentSignInsSettings"></div>' });
  const { window } = app;
  window.auth = { currentUser: { uid: "u1", getIdToken: async () => "token" } };
  return { window, document: app.document, signIns: window.App.agentSignIns };
}

function reply(data, status = 200) {
  return { ok: status < 400, status, json: async () => data };
}

const WHATSAPP = { site: "web.whatsapp.com", name: "WhatsApp", since: "2026-11-02" };
const GITHUB = { site: "github.com", name: "GitHub", since: "" };

describe("the list of sign-ins", () => {
  it("shows each site with its host name and first day, the names as data", async () => {
    const { window, document, signIns } = setup();
    window.fetch = vi.fn(async () => reply({ sign_ins: [WHATSAPP, GITHUB] }));
    await signIns.load(true);
    const [url, options] = window.fetch.mock.calls[0];
    expect(url).toBe("/agent/workspace/sign-ins");
    expect(options.headers.Authorization).toBe("Bearer token");
    const rows = [...document.querySelectorAll(".agent-sign-in")];
    expect(rows.map(row => row.querySelector(".agent-sign-in-name").textContent)).toEqual(["WhatsApp", "GitHub"]);
    expect(rows[0].querySelector(".agent-sign-in-site").textContent).toBe("web.whatsapp.com");
    expect(rows[0].querySelector(".agent-sign-in-since").textContent).toMatch(/^Since .*2/);
    // No day noted: no day shown.
    expect(rows[1].querySelector(".agent-sign-in-since")).toBeNull();
    expect(rows[0].querySelector(".agent-sign-in-name").hasAttribute("data-i18n-skip")).toBe(true);
    expect(document.querySelector(".agent-sign-ins-status").textContent).toBe("");
  });

  it("says how a site gets there while there is none", async () => {
    const { window, document, signIns } = setup();
    window.fetch = vi.fn(async () => reply({ sign_ins: [] }));
    await signIns.load(true);
    expect(document.querySelector(".agent-sign-ins-list").hidden).toBe(true);
    expect(document.querySelector(".agent-sign-ins-status").textContent).toContain("the Agent notes it here");
  });

  it("takes a site off the list and shows what is left", async () => {
    const { window, document, signIns } = setup();
    window.fetch = vi.fn(async () => reply({ sign_ins: [WHATSAPP, GITHUB] }));
    await signIns.load(true);
    window.fetch = vi.fn(async () => reply({ sign_ins: [GITHUB] }));
    document.querySelector(".agent-sign-in-remove").click();
    await vi.waitFor(() => expect(document.querySelectorAll(".agent-sign-in")).toHaveLength(1));
    const [url, options] = window.fetch.mock.calls[0];
    expect(url).toBe("/agent/workspace/sign-ins/remove");
    expect(JSON.parse(options.body)).toEqual({ site: "web.whatsapp.com" });
    expect(document.querySelector(".agent-sign-in-name").textContent).toBe("GitHub");
  });

  it("reads the list again only after a while unless told to", async () => {
    const { window, signIns } = setup();
    window.fetch = vi.fn(async () => reply({ sign_ins: [] }));
    await signIns.load(true);
    await signIns.load();
    expect(window.fetch).toHaveBeenCalledTimes(1);
    await signIns.load(true);
    expect(window.fetch).toHaveBeenCalledTimes(2);
  });
});

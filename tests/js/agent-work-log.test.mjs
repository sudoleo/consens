import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The work log section of the activity sidebar (agent-work-log.js, admins,
// audit mode; agent_work_log.py).
const chatId = "c".repeat(32), turnId = "d".repeat(32), agentId = "a".repeat(32);
const reviewer = { id: agentId, seq: 1, status: "completed", kind: "audit", title: "Review · Claude",
  model: { model: "anthropic/claude", label: "Claude" }, duration_ms: 1200 };
const entries = [
  { seq: 1, at: "2026-10-25T18:20:31Z", actor: "app", kind: "start", name: "", data: "app", format: "json",
    content: '{"question":"How tall?"}', chars: 24 },
  { seq: 2, at: "2026-10-25T18:20:35Z", actor: "agent", kind: "tool", name: "read_source", data: "web", format: "text",
    content: "Page begins", chars: 40000, ref: "work-log/u/c/t/000002" },
  { seq: 3, at: "2026-10-25T18:20:40Z", actor: "worker:abc", kind: "step", name: "openai/gpt", data: "agent", format: "json",
    content: '{"text":"330 m"}', chars: 16 },
];
function boot(status = "succeeded") {
  return loadScripts(["static/js/request-deadline.js", "static/js/agent-work-log.js", "static/js/agent-delegation.js"], {
    body: '<div id="agentAnswerActivity"></div>', before(w) {
      w.auth = { currentUser: { uid: "owner", getIdToken: async () => "token" } };
      w.App = { runRegistry: { isAuthCurrent: c => c.auth.uid === w.auth.currentUser.uid } };
      w.fetch = vi.fn(async url => ({ ok: true, json: async () => url.includes("/work-log/2")
        ? { ...entries[1], content: "Page begins and goes on to the end." }
        : url.includes("/work-log") ? { entries, has_more: false, incomplete: false, status: "completed" }
        : { agents: [{ ...reviewer, status: (w.runStatus || status) === "running" ? "working" : "completed" }],
            status: w.runStatus || status } }));
    } });
}
const settle = () => new Promise(resolve => setTimeout(resolve, 0));
const logCalls = w => w.fetch.mock.calls.filter(([url]) => url.includes("/work-log"));
// Without a matchMedia the window counts as wide, where the panel stands open
// by itself (2026-10-28); the toggle opens it only where it is not.
function openPanel(d) {
  const toggle = d.querySelector(".agent-sidebar-toggle");
  if (toggle.getAttribute("aria-expanded") !== "true") toggle.click();
}
function open(details) {
  details.open = true;
  details.dispatchEvent(new details.ownerDocument.defaultView.Event("toggle"));
}

describe("Agent work log", () => {
  it("loads only when opened and lists each entry with who, what and where it came from", async () => {
    const { window: w, document: d } = boot();
    w.App.agentDelegation.project({ chatId, turnId, running: false, workLog: true });
    await settle();
    openPanel(d);
    const host = d.querySelector(".agent-work-log-host");
    expect(host.hidden).toBe(false);
    // The raw log is the operator's (UX audit F5, style.css .admin-only):
    // the activity tells a Pro account the same run in words.
    expect(host.classList.contains("admin-only")).toBe(true);
    // The rows go above it: it stays the list's last section.
    expect(d.querySelector(".agent-session-list").lastElementChild).toBe(host);
    expect(host.querySelector(".agent-work-log-summary").textContent).toContain("Work log");
    expect(logCalls(w)).toHaveLength(0);
    open(host.querySelector(".agent-work-log"));
    await vi.waitFor(() => expect(host.querySelectorAll(".agent-work-log-entry")).toHaveLength(3));
    expect(logCalls(w)[0][0]).toContain(`/agent/chats/${chatId}/turns/${turnId}/work-log?after=0&limit=200`);
    const rows = [...host.querySelectorAll(".agent-work-log-entry")];
    expect(rows.map(row => [row.querySelector(".agent-work-log-actor").textContent, row.querySelector(".agent-work-log-kind").textContent,
      row.querySelector(".agent-work-log-data").textContent])).toEqual([["App", "Start"], ["Agent", "Tool"], ["Worker", "Step"]]
      .map(([actor, kind], index) => [actor, kind, ["App", "Web", "Model"][index]]));
    // Outside content is marked as data.
    expect(rows[1].querySelector(".agent-work-log-data").classList.contains("is-untrusted")).toBe(true);
    expect(rows[0].querySelector(".agent-work-log-data").classList.contains("is-untrusted")).toBe(false);
    expect(host.querySelector(".agent-work-log-count").textContent).toBe("3");
    // A finished run whose log has no end entry lost its last entries.
    expect(host.querySelector(".agent-work-log-status").textContent).toBe("Some entries could not be saved; the log is incomplete.");
    // JSON reads indented; content is built when an entry opens.
    expect(rows[0].querySelector("pre")).toBeNull();
    open(rows[0].querySelector("details"));
    expect(rows[0].querySelector("pre").textContent).toBe('{\n  "question": "How tall?"\n}');
    // A shortened entry loads whole on request.
    open(rows[1].querySelector("details"));
    expect(rows[1].querySelector(".agent-work-log-note").textContent).toContain("11");
    rows[1].querySelector(".agent-work-log-more").click();
    await vi.waitFor(() => expect(rows[1].querySelector("pre").textContent).toBe("Page begins and goes on to the end."));
    expect(rows[1].querySelector(".agent-work-log-more")).toBeNull();
  });

  // A turn whose only content in the panel is its log (audit, answer check
  // off) opens no empty panel for an account that cannot see the log (F5).
  it("keeps the panel of a turn with only a log to the admins who see it", async () => {
    const { window: w, document: d } = loadScripts(["static/js/request-deadline.js", "static/js/agent-work-log.js", "static/js/agent-delegation.js"], {
      body: '<div id="agentAnswerActivity"></div>', before(win) {
        win.auth = { currentUser: { uid: "owner", getIdToken: async () => "token" } };
        win.App = { runRegistry: { isAuthCurrent: () => true } };
        win.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ agents: [], status: "succeeded" }) }));
      } });
    w.App.agentDelegation.project({ chatId, turnId, running: false, workLog: true });
    await settle();
    expect(d.querySelector(".agent-sidebar-toggle").hidden).toBe(true);
    expect(d.getElementById("agentSidebar").hidden).toBe(true);
    d.body.classList.add("viewer-is-admin");
    w.App.agentDelegation.project({ chatId, turnId, running: false, workLog: true });
    await settle();
    expect(d.querySelector(".agent-sidebar-toggle").hidden).toBe(false);
  });

  it("stays hidden for a turn without a log and never asks for one", async () => {
    const { window: w, document: d } = boot();
    w.App.agentDelegation.project({ chatId, turnId, running: false });
    await settle();
    openPanel(d);
    expect(d.querySelector(".agent-work-log-host").hidden).toBe(true);
    expect(logCalls(w)).toHaveLength(0);
  });

  it("stops following a turn once another one shows, the panel closes or the account changes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { window: w, document: d } = boot("running");
      w.App.agentDelegation.project({ chatId, turnId, running: true, workLog: true });
      openPanel(d);
      open(d.querySelector(".agent-work-log"));
      await vi.waitFor(() => expect(logCalls(w)).toHaveLength(1));
      // Another turn, without a log: the first one is no longer polled.
      w.App.agentDelegation.project({ chatId, turnId: "e".repeat(32), running: false });
      const before = logCalls(w).length;
      await vi.advanceTimersByTimeAsync(10_000);
      expect(logCalls(w).length).toBe(before);
      expect(d.querySelector(".agent-work-log-host").childElementCount).toBe(0);
      // Back to it, closed panel: no polling either.
      w.App.agentDelegation.project({ chatId, turnId, running: true, workLog: true });
      await vi.waitFor(() => expect(logCalls(w).length).toBeGreaterThan(before));
      d.querySelector(".agent-sidebar-close").click();
      await vi.advanceTimersByTimeAsync(1000);
      const closed = logCalls(w).length;
      await vi.advanceTimersByTimeAsync(10_000);
      expect(logCalls(w).length).toBe(closed);
      // Another account: nothing of this one stays.
      w.App.agentWorkLog.reset(d.querySelector(".agent-work-log-host"));
      expect(d.querySelector(".agent-work-log-host").hidden).toBe(true);
      expect(d.querySelector(".agent-work-log-host").childElementCount).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("says it waits while a running turn has no entries yet", async () => {
    const { window: w, document: d } = loadScripts(["static/js/request-deadline.js", "static/js/agent-work-log.js", "static/js/agent-delegation.js"], {
      body: '<div id="agentAnswerActivity"></div>', before(win) {
        win.auth = { currentUser: { uid: "owner", getIdToken: async () => "token" } };
        win.App = { runRegistry: { isAuthCurrent: () => true } };
        win.fetch = vi.fn(async url => ({ ok: true, json: async () => url.includes("/work-log")
          ? { entries: [], has_more: false, incomplete: false } : { agents: [{ ...reviewer, status: "working" }], status: "running" } }));
      } });
    w.App.agentDelegation.project({ chatId, turnId, running: true, workLog: true });
    openPanel(d);
    open(d.querySelector(".agent-work-log"));
    await vi.waitFor(() => expect(d.querySelector(".agent-work-log-status").textContent).toBe("Waiting for the first entries…"));
  });

  it("follows a running turn and loads its last entries when it ends", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { window: w, document: d } = boot("running");
      w.App.agentDelegation.project({ chatId, turnId, running: true, workLog: true });
      openPanel(d);
      open(d.querySelector(".agent-work-log"));
      await vi.waitFor(() => expect(logCalls(w)).toHaveLength(1));
      await vi.advanceTimersByTimeAsync(3100);
      await vi.waitFor(() => expect(logCalls(w).length).toBeGreaterThanOrEqual(2));
      // Polling continues after the last seen entry.
      expect(logCalls(w).at(-1)[0]).toContain("after=3");
      // The run ends: once the server says so, the log loads its last entries and stops.
      w.runStatus = "succeeded";
      const before = logCalls(w).length;
      w.App.agentDelegation.project({ chatId, turnId, running: false, workLog: true });
      await vi.waitFor(() => expect(logCalls(w).length).toBeGreaterThan(before));
      const after = logCalls(w).length;
      await vi.advanceTimersByTimeAsync(10_000);
      expect(logCalls(w).length).toBe(after);
    } finally {
      vi.useRealTimers();
    }
  });
});

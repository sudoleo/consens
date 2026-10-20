import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// "Working for 9s" ticks in a field of fixed width: the chevron and the
// model icons after it stay put while it counts and when it ends (Apple
// audit A7). The words themselves do not change.
describe("activity clock", () => {
  it("keeps its words and sizes its time slot by unit, with the other verb reserved", () => {
    vi.useFakeTimers();
    const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="host"></div>' });
    const host = app.document.getElementById("host");
    const activity = app.window.App.agentActivity;
    activity.render(host, { running: true, elapsedMs: 9000, status: "running", events: [] });
    const title = host.querySelector(".agent-activity-title");
    const time = title.querySelector(".agent-activity-time");
    const verb = title.querySelector(".agent-activity-verb");
    expect(title.textContent).toBe("Working for 9s");
    // A live clock holds the minutes slot from its first second.
    expect(time.dataset.unit).toBe("minutes");
    expect(verb.dataset.ghost).toBe("Thought for");
    activity.render(host, { running: true, elapsedMs: 10000, status: "running", events: [] });
    expect(title.textContent).toBe("Working for 10s");
    expect(time.dataset.unit).toBe("minutes");
    expect(title.querySelector(".agent-activity-time")).toBe(time);
    activity.render(host, { running: true, elapsedMs: 72000, status: "running", events: [] });
    expect(title.textContent).toBe("Working for 1m 12s");
    expect(time.dataset.unit).toBe("minutes");
    activity.render(host, { running: false, elapsedMs: 72000, status: "succeeded", events: [] });
    expect(title.textContent).toBe("Thought for 1m 12s");
    expect(verb.dataset.ghost).toBe("Working for");
    activity.render(host, { running: false, elapsedMs: 72000, status: "failed", events: [] });
    expect(title.textContent).toBe("Failed after 1m 12s");
    expect(verb.dataset.ghost).toBeUndefined();
    activity.dispose(host);
    // A saved turn that never ticked here sizes the slot by its own value.
    const saved = app.document.createElement("div");
    activity.render(saved, { running: false, elapsedMs: 18000, status: "succeeded", events: [] });
    expect(saved.querySelector(".agent-activity-time").dataset.unit).toBe("seconds");
    vi.useRealTimers();
    app.dom.window.close();
  });
});
